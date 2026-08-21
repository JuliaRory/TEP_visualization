import QtQuick 2.5
import Resonance 3.0
import QtQuick.Controls 1.4

ApplicationWindow {
    id: root
    property string current_record_filename: ""

    function isRecorderService(serviceName) {
        return serviceName === "Recorder"
    }

    function applyRecorderFilename(filename) {
        if (!filename) {
            print("--- recorder filename is empty ---")
            return false
        }

        rec_filename.value = filename
        root.current_record_filename = filename
        recorder.hdfFileName = filename
        print("--- recorder filename: " + filename)
        return true
    }

    function startRecorder(command, filename) {
        applyRecorderFilename(filename || root.current_record_filename || rec_filename.value)
        recorder.start()

        print("--- " + command + " the record --- ")
    }

    function stopRecorder() {
        recorder.finish()
        print("--- finish the record --- ")
    }
    
    Component.onCompleted: {
        ResonanceApp.setServiceName('Resonance-control')    // сервис для для контроля резонансовых модулей
    }

    Parameters {
        Stream {
            id: control_message     
            name: 'controlSignal'                           // имя потока
            label: 'controlSignal' 
        }
        String {
            id: service_name
            name: "service name"
            label: "service name"
            value: "signalGenerator"
        }
        String {
            id: stream_name
            name: "stream_name"
            label: "stream_name"
            value: "generated"
        }
        String {
            id: rec_filename
            name: "rec_filename"
            label: "rec_filename"
            //value: "C:\\Users\\hodor\\Documents\\lab-MSU\\Works\\2025.10_TMS\\TEP_visualization\\data\\records\\rec-$$$.h5"
            value: "D:\\Resonance\\TEP_visualization\\data\\records\\rec-$$$.h5"
        }


    }

    MessageReceiver {  
        id: controlSignal_receiver 
		sourceInfo: control_message.desiredStream

        onMessage: {
            // message — это JSON вида:
            // {"service": "service_name", "type": "parameter", "parameter": "parameter_name", "value": "200"}
            // {"service": "service_name", "type": "command", "command": "command_name", "stream": "stream_name"}
            
            var msg = JSON.parse(text);

            let service = ResonanceApp.getService(msg.service)

            print(text)

            if (msg.type === "parameter") {
                let param = msg.param || msg.parameter
                print(param, msg.value);
                service.sendParameter(param, msg.value);
                
            }
           

            if (msg.type === "command") {
                if (isRecorderService(msg.service)) {
                    if (msg.command == "start") {
                        print("--- " + msg.command + " the record --- ");
                        service.sendTransition(msg.command)
                    }

                    if (msg.command == "start_rec") {
                        startRecorder("start_rec", msg.filename)
                    }

                    if (msg.command == "stop") {
                       service.sendTransition(msg.command);
                       print("--- finish the record --- ")
                    }
                } else {
                    service.sendTransition(msg.command)
                }
            }

            if (msg.type == "check") {
                print("check");
                if (service) {print("YES");}
                else {print("NO");}

            }
            
        }
    }

    Recording {  // запускает qml
            id: recorder
            hdfFileName: rec_filename.value
            //eventStreamDiscovery: 'discover:///?stream=events&name=Stimulus%20Presentation'
			use_nvx: true
            service_name: service_name.value
            stream_name: stream_name.value
			use_speed: false
		}
}
