import ctypes
import platform
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RESONANCE_DIR = "C:/Users/hodor/Documents/lab-MSU/Resonance2026/msvc64"


def _candidate_resonance_dirs():
    for env_name in ("RESONANCE_DIR",):
        value = os.environ.get(env_name)
        if value:
            yield value

    resonance_path = os.environ.get("RESONANCE_PATH", "")
    for path in resonance_path.split(os.pathsep):
        if path:
            yield os.path.dirname(path) if os.path.basename(path).lower() == "bin" else path

    yield DEFAULT_RESONANCE_DIR


def _find_resonance_bin():
    for resonance_dir in _candidate_resonance_dirs():
        bin_dir = os.path.join(resonance_dir, "bin")
        if os.path.exists(os.path.join(bin_dir, "ResonanceForeignDriver.dll")):
            return os.path.normpath(bin_dir)
    return BASE_DIR

class Driver:
    def __init__(self, name):
        
        if platform.system() == "Windows":
            bin_dir = _find_resonance_bin()
            qt_bin_dir = os.path.abspath(os.path.join(bin_dir, "..", "qt", "bin"))

            os.environ["RESONANCE_PATH"] = os.pathsep.join([bin_dir, qt_bin_dir])
            os.environ["PATH"] = os.pathsep.join(
                path for path in [bin_dir, qt_bin_dir, os.environ.get("PATH", "")] if path
            )
            for dll_dir in (bin_dir, qt_bin_dir, BASE_DIR):
                if os.path.isdir(dll_dir):
                    try:
                        os.add_dll_directory(dll_dir)
                    except (FileNotFoundError, OSError):
                        pass

            dll_path = os.path.join(bin_dir, "ResonanceForeignDriver.dll")
            ctypes.windll.kernel32.LoadLibraryA(dll_path.encode("utf-8"))
            self._lib = ctypes.cdll.LoadLibrary(dll_path)
            
        else:
            self._lib = ctypes.CDLL("libResonanceForeignDriver.so")
        
        self._lib.setUp.argtypes = [ctypes.c_char_p]
        
        self._lib.pollEvents.argtypes = []
        
        self._lib.outputMessageStream.restype = ctypes.c_size_t
        self._lib.outputMessageStream.argtypes = [ctypes.c_char_p]
        
        self._lib.sendMessage.argtypes = (ctypes.c_size_t, ctypes.c_char_p)
        
        self._messageCallback = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_uint64)
        self._dataCallback = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_double), ctypes.c_uint, ctypes.c_uint, ctypes.c_uint64)
        
        self._callbacks = []
        
        self._lib.inputMessageStream.argtypes = (ctypes.c_char_p, self._messageCallback)
        self._lib.inputDataStream.argtypes = (ctypes.c_char_p, self._dataCallback)
        
        self._lib.loadConfig.argtypes = [ctypes.c_char_p]
        
        self._lib.setUp(bytes(name, 'utf-8'))
        
    def loadConfig(self, fileName):
        self._lib.loadConfig(bytes(fileName, 'utf-8'))
        
    def pollEvents(self):
        self._lib.pollEvents()
        
    def outputMessageStream(self, name):
        id = self._lib.outputMessageStream(bytes(name, 'utf-8'))
        
        def sendMessage(message):
            self._lib.sendMessage(id, bytes(message, 'utf-8'))
            
        return sendMessage
    
    
    def inputMessageStream(self, name, callback):
        cb = self._messageCallback(callback)
        self._callbacks.append(cb)
        self._lib.inputMessageStream(bytes(name, 'utf-8'), cb)
        
    def inputDataStream(self, name, callback, no_numpy=False):
        def cb_wrapper(data, channels, samples, timestamp):
            if no_numpy:
                arr = []
                i = 0
                for s in range(0, samples):
                    v = []
                    for c in range(0, channels):
                        v.append(data[i])
                        i += 1
                    arr.append(v)
            else:
                import numpy as np
                arr = np.zeros((samples, channels))
                i = 0
                for s in range(0, samples):
                    for c in range(0, channels):
                        arr[s,c] = data[i]
                        i += 1
            callback(arr, timestamp)
            
        cb = self._dataCallback(cb_wrapper)
        self._callbacks.append(cb)
        self._lib.inputDataStream(bytes(name, 'utf-8'), cb)
