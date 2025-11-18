import QtQml.StateMachine 1.0 as DSM
import Resonance 3.0

DSM.StateMachine {
    id: root
    initialState: st_initial

    property string eegMode: 'Normal' // EEG recording mode
	property alias isLaunched: stLAUNCHER_running.active 
	
	signal finish
	signal launched

    DSM.State { // INITIAL STATE
        id: st_initial

        // если nvx включён, то перейти далее
        DSM.SignalTransition {
            signal: st_initial.entered
            guard: start_nvx.ready
            targetState: stLAUNCHER
        }

        // если nvx выключен, то перейти ко включению nvx
        DSM.SignalTransition {
            signal: st_initial.entered
            guard: !start_nvx.ready
            targetState: start_nvx
        }
    }

    DSM.State {
        id: st_launched
        DSM.SignalTransition {
            signal: root.finish
            targetState: st_final
        }

        DSM.State {
            id: stLAUNCHER
            initialState: stLAUNCHER_set_mode

            // послать параметр для переключения nvx136 в режим записи ЭЭГ
            DSM.State {
                id: stLAUNCHER_set_mode

                onEntered: {
					let nvx = ResonanceApp.getService('nvx136');
					if(nvx){ nvx.sendParameter('mode', root.eegMode)}
				}

                DSM.TimeoutTransition {
                    timeout: 200
                    targetState: stLAUNCHER_start_nvx
                }
            }

            DSM.State { // включить nvx136
                id: stLAUNCHER_start_nvx

                onEntered: {
                    let nvx = ResonanceApp.getService('nvx136');
					if(nvx){ nvx.sendTransition('start')}
                }

                DSM.TimeoutTransition {
                    timeout: 1000
                    targetState: stLAUNCHER_running
                }
            }

			DSM.State {
				id: stLAUNCHER_running

				onEntered: { root.launched()}

				DSM.SignalTransition {
					signal: root.finish // the stop signal from a button..
					targetState: st_final
				}
			}
        }
	}
	
	DSM.FinalState {
        id: st_final
        onEntered: {
			let nvx = ResonanceApp.getService('nvx136');
            if (nvx) {nvx.sendTransition('stop')}
        }
    }

    StartNVX136 { // запускает qml 
         id: start_nvx

         DSM.SignalTransition {
             signal: start_nvx.finished
             targetState: stLAUNCHER
         }
    }
}
