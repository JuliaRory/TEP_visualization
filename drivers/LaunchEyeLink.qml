import QtQml.StateMachine 1.0 as DSM
import Resonance 3.0

DSM.StateMachine {
    id: root
    initialState: st_initial

	property alias isLaunched: stLAUNCHER_running.active 
	
	signal finish
	signal launched

    DSM.State { // INITIAL STATE
        id: st_initial

        // если nvx включён, то перейти далее
        DSM.SignalTransition {
            signal: st_initial.entered
            guard: start_eyelink.ready
            targetState: stLAUNCHER
        }

        // если nvx выключен, то перейти ко включению nvx
        DSM.SignalTransition {
            signal: st_initial.entered
            guard: !start_eyelink.ready
            targetState: start_eyelink
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
            initialState: stLAUNCHER_wait
			
			// послать параметр для переключения nvx136 в режим записи ЭЭГ
            DSM.State {
                id: stLAUNCHER_wait

                DSM.TimeoutTransition {
                    timeout: 1000
                    targetState: stLAUNCHER_start_eyelink
                }
            }
			
            DSM.State { // включить nvx136
                id: stLAUNCHER_start_eyelink

                onEntered: {
                    let eyelink = ResonanceApp.getService('eyelink');
					if(eyelink){ eyelink.sendTransition('start')}
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
			let eyelink = ResonanceApp.getService('eyelink');
            if (eyelink) {eyelink.sendTransition('stop')}
        }
    }

    StartEyeLink { // запускает qml 
         id: start_eyelink

         DSM.SignalTransition {
             signal: start_eyelink.finished
             targetState: stLAUNCHER
         }
    }
}
