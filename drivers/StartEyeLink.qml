import QtQml.StateMachine 1.0 as DSM
import Resonance 3.0


DSM.State {
	id: start_136_nvx
	
	property string nvx1_device: 'Device #0'
	
	property bool configured: true //nvx1_param_device.matches
	property bool ready: nvx1Present.present //&& configured
	
	initialState: start_136_nvx_initial
	
	DSM.FinalState { id: start_136_nvx_done }
	DSM.State { 
		id: start_136_nvx_initial
	
		DSM.SignalTransition {
			signal: start_136_nvx_initial.entered
			guard: !nvx1Present.present
			targetState: start_nvx_1
		}
	
		DSM.SignalTransition {
			signal: start_136_nvx_initial.entered
			guard: nvx1Present.present && !start_136_nvx.configured
			targetState: configure_both_nvx
		}
		
		DSM.SignalTransition {
			signal: start_136_nvx_initial.entered
			guard: start_136_nvx.ready
			targetState: start_136_nvx_done
		}
		
		DSM.TimeoutTransition {
			timeout: 750
			targetState: start_136_nvx_initial
		}
	}
	
	DSM.State {
		id: start_nvx_1
		onEntered: {
			launchNVX1.start("..\\`eyeLink.bat")
		}
		
		DSM.TimeoutTransition {
			timeout: 5000
			targetState: start_136_nvx_initial
		}
	}
	
	
	DSM.State {
		id: configure_both_nvx
		onEntered: {
			let nvx = ResonanceApp.getService('eyelink');
			
			//if(nvx){
			//	nvx.sendParameter('mode', start_136_nvx.nvx_mode)
				//nvx.sendTransition('rescan')
				//nvx.sendParameter('device', start_136_nvx.nvx1_device)
			//}
		}
		
		DSM.TimeoutTransition {
			timeout: 1250
			targetState: start_136_nvx_initial
		}
	}
	
	

	ParameterInspector {
		id: nvx1_param_device
		serviceName: "eyelink"
		parameterName: "device"
		expectedValue: start_136_nvx.nvx1_device
	}

	
	Process {id: launchNVX1}
	
	ServiceInspector {
        id: nvx1Present
        serviceName: "eyelink"
    }

	
}