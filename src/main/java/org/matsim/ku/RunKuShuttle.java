package org.matsim.ku;

import org.matsim.api.core.v01.Scenario;
import org.matsim.core.config.Config;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.controler.Controler;
import org.matsim.core.scenario.ScenarioUtils;

/**
 * วิธีเรียก:
 *   java -Xmx6g -cp target/*.jar org.matsim.ku.RunKuShuttle \
 *        config.xml output/base input/transitSchedule.xml.gz input/transitVehicles.xml.gz
 *
 * อาร์กิวเมนต์ 2-4 เป็นตัวเลือก ใช้ตอนรันหลายซีนาริโอเทียบกัน
 */
public class RunKuShuttle {

    public static void main(String[] args) {
        String configFile = args.length > 0 ? args[0] : "config.xml";
        Config config = ConfigUtils.loadConfig(configFile);

        if (args.length > 1) {
            config.controller().setOutputDirectory(args[1]);
        }
        if (args.length > 3) {
            config.transit().setTransitScheduleFile(args[2]);
            config.transit().setVehiclesFile(args[3]);
        }

        Scenario scenario = ScenarioUtils.loadScenario(config);
        Controler controler = new Controler(scenario);
        controler.run();

        System.out.println("เสร็จแล้ว — วิเคราะห์ต่อด้วย:");
        System.out.println("  python3 scripts/analyze_events.py "
                + config.controller().getOutputDirectory());
    }
}
