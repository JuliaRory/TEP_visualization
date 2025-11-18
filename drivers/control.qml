import QtQuick 2.5
import Resonance 3.0
import QtQuick.Controls 1.4

ApplicationWindow {
    id: root
    
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
            value: "C:\\Users\\hodor\\Documents\\lab-MSU\\Works\\2025.10_TMS\\TEP_visualization\\data\\records\\rec-$$$.h5"
        }

    }

    MessageReceiver {  
        id: controlSignal_receiver 
		sourceInfo: control_message.desiredStream

        onMessage: {
            // message — это JSON вида:
            // {"service": "service_name", "type": "parameter", "parameter": "parameter_name", "value": "200"}
            // {"service": "service_name", "type": "command", "command": "command_name"}
            
            var msg = JSON.parse(text);

            let service = ResonanceApp.getService(msg.service)
            //service.sendParameter(msg.parameter, msg.value)
            //service.sendTransition(msg.command)
            print(text)
            if (msg.type === "command") {
                if (msg.command == "!terminate") {service.sendTransition(msg.parameter, msg.command)};
                
                if (msg.command == "start") {
                    //rec_filename = "C:/Users/hodor/Documents/lab-MSU/Works/2025.10_TMS/TEP_visualization/data/records/rec-$$$.h5"; //msg.filename;
                    //print(rec_filename.text);
                    //service_name.value = msg.
                    recorder.start(); 
                    print("--- start the record --- ");
                    };

                if (msg.command == "stop") {
                    recorder.finish();
                    print("--- finish the record --- ");
                    };
                }
            if (msg.type == "parameter") 
                {print("parameter"); 
                }
            
        }
    }

    Recording {  // запускает qml
            id: recorder
            //hdfFileName: rec_filename.text
            //eventStreamDiscovery: 'discover:///?stream=events&name=Stimulus%20Presentation'
			use_nvx: true
            service_name: service_name.value
            stream_name: stream_name.value
			use_speed: false
		}
}