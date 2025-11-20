import QtQml.StateMachine 1.0 as DSM
import Resonance 3.0

DSM.StateMachine {
    id: root
    initialState: st_initial

    property string hdfFileName: 'keklol-$$.hdf5'
    property string eegMode: 'Normal' // EEG recording mode
	property string eventStreamDiscovery: 'discover:///?stream=events&name=WorkflowControler' //WHAT IS IT?? 

    property int eegRecordCounter: 1 // WHAT IS IT?? 
	
	property bool use_nvx: false
	property bool use_speed: false

    property alias runningRecord: stRECORD_running.active // идёт запись ээг, если находится в состоянии stRECORD_running
    property alias isLaunched: st_launched.active // запущен, если находится в состоянии st_launched

    signal startRecord  // WHAT IS IT? to mark the start eeg recording?
    signal finish // WHAT IS IT? to mark the end of eeg recording?
    signal startEeg // not sure that i still need it
	
	signal startedEeg

    Recorder { 
        id: recorder
    }

    DSM.State { // INITIAL STATE
        id: st_initial

        // если nvx включён, то перейти далее
        DSM.SignalTransition {
            signal: st_initial.entered
            guard: start_nvx.ready
            targetState: st_start_recorder
        }

        // если nvx выключен, то перейти ко включению nvx
        DSM.SignalTransition {
            signal: st_initial.entered
            guard: !start_nvx.ready
            targetState: start_nvx
        }
    }
	
	
    DSM.State {
        id: st_start_recorder
        onEntered: {
            recorder.openFile(root.hdfFileName)
            recorder.addStream(root.eventStreamDiscovery) // WHY?
        }

        DSM.SignalTransition {
            signal: st_start_recorder.entered
            targetState: st_record
        }
    }
	

    DSM.State {
        id: st_launched
		
        DSM.SignalTransition {
            signal: root.finish
            targetState: st_final
        }

        DSM.State {
            id: st_record
            initialState: stRECORD_set_mode_eeg

            // послать параметр для переключения nvx136 в режим записи ЭЭГ
            DSM.State {
                id: stRECORD_set_mode_eeg

                onEntered: {
					if (root.use_nvx)
					{
						let nvx = ResonanceApp.getService('nvx136');
						if(nvx){ nvx.sendParameter('mode', root.eegMode)}
					}
					
					if (root.use_speed)
					{
						let speed = ResonanceApp.getService('speed');
						if(speed){ speed.sendTransition('prepare')}
					}
				}

                DSM.TimeoutTransition {
                    timeout: 500
                    targetState: stRECORD_start_devices
                }
            }

            DSM.State { // включить nvx136
                id: stRECORD_start_devices

                onEntered: {
                    if (root.use_nvx)
					{
						let nvx = ResonanceApp.getService('nvx136');
						if(nvx){ nvx.sendTransition('start')}
					}
					if (root.use_speed)
					{
						let speed = ResonanceApp.getService('speed');
						if(speed){ speed.sendTransition('start')}
					}
					
                }

                DSM.TimeoutTransition {
                    timeout: 1000
                    targetState: stRECORD_start_recording
                }
            }


            DSM.State {
                id: stRECORD_start_recording

                onEntered: {
                    if (root.use_nvx) {recorder.addStream('discover:///?stream=eeg&name=nvx136', 'eeg')}
                    if (root.use_speed) {recorder.addStream('discover:///?stream=out_raw&name=SPEED')}
					
					root.eegRecordCounter += 1 // ЗАЧЕМ ЭТОТ СЧЁТЧИК???
					
                }

                DSM.SignalTransition { // what is it?..
                    signal: recorder.streamsChanged
                    guard: {
                        let nvx1Found = false;
                        let nvx1 = ResonanceApp.getService('nvx136');

                        recorder.recording.forEach((info) => {
                            if(info.uid === nvx1.uid){
                                nvx1Found = true;
                            }
                        } )

                        return nvx1Found;
                    }
                    targetState: stRECORD_running
                }
            }

			DSM.State {
				id: stRECORD_running

				onEntered: { root.startedEeg()} // WHAT IS IT??? 

				DSM.SignalTransition {
					signal: root.finish // the stop signal from a button
					targetState: st_final
				}

			}
        }

    DSM.FinalState {
        id: st_final
        onEntered: { recorder.closeFile()}
    }

    StartNVX136 { // запускает qml 
         id: start_nvx

         DSM.SignalTransition {
             signal: start_nvx.finished
             targetState: st_start_recorder
         }
    }


}
}
