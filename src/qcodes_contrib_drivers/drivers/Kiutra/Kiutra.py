from time import sleep

from kiutra_api.controller_interfaces import (
    ADRControl,
    CryostatControl,
    HeaterControl,
    MagnetControl,
    SampleControl,
    TemperatureControl,
)
from kiutra_api.device_interfaces import Magnet
from qcodes.instrument import Instrument


class Kiutra(Instrument):
    def __init__(self, name: str, host_ip_address: str) -> None:
        super().__init__(
            name, metadata={}, label="kiutra"
        )  # Calls Instrument.__init__(name)

        self.cryostat_control = CryostatControl(
            device="cryostat",
            host=host_ip_address,
        )
        self.sample_control = SampleControl(
            device="sample_loader",
            host=host_ip_address,
        )
        self.temperature_control = TemperatureControl(
            device="temperature_control",
            host=host_ip_address,
        )
        self.adr_control = ADRControl(
            device="adr_control",
            host=host_ip_address,
        )
        self.heater_control = HeaterControl(
            device="sample_heater",
            host=host_ip_address,
        )
        self.magnet_control = MagnetControl(
            device="sample_magnet",
            host=host_ip_address,
        )
        self.magnet_power_supply_1 = Magnet(
            device="mps_1",
            host=host_ip_address,
        )
        self.magnet_power_supply_2 = Magnet(
            device="mps_2",
            host=host_ip_address,
        )

        self.add_parameter(
            name="sample_stage_temperature",
            unit="K",
            label="sample_stage_temperature",
            get_cmd=lambda: self.TemperatureControl.kelvin,
        )
        self.add_parameter(
            name="sample_magnetic_field",
            unit="T",
            label="sample_magnetic_field",
            get_cmd=lambda: self.MagnetControl.field,
            set_cmd=lambda field: self.stabilize_at_magnetic_field(
                setpoint_magnetic_field=field
            ),
        )
        self.add_parameter(
            name="magnet_power_supply_1_field",
            unit="T",
            label="magnet_power_supply_1_field",
            get_cmd=lambda: self.magnet_power_supply_1.field,
        )
        self.add_parameter(
            name="magnet_power_supply_2_field",
            unit="T",
            label="magnet_power_supply_2_field",
            get_cmd=lambda: self.magnet_power_supply_2.field,
        )
        self.add_parameter(
            name="sample_heater_power",
            unit="W",
            label="sample_heater_power",
            get_cmd=lambda: self.HeaterControl.power,
        )

    def get_idn(self) -> dict[str, str | None]:
        return {"model": "Kiutra", "Host": self.host_ip_address}

    def start_magnetic_field_sweep(
        self,
        setpoint_magnetic_field: float,
        magnetic_field_ramp_rate: float | None = None,
    ) -> None:
        if magnetic_field_ramp_rate is None:
            magnetic_field_ramp_rate = self.get_magnetic_field_ramp_rate()

        self.MagnetControl.start(
            setpoint=setpoint_magnetic_field, ramp=magnetic_field_ramp_rate
        )
        print(
            f"Magnetic field ramping to {setpoint_magnetic_field} T at {magnetic_field_ramp_rate} T/min"
        )

    def get_magnetic_field_ramp_rate(self) -> float:
        """We choose a magnetic field ramp rate based on the reccommedantion from Kiutra Operator's Manual p.30.
        Ramp rate is in Tesla/minute."""

        if self.sample_stage_temperature() < 1:
            return 0.1
        elif self.sample_stage_temperature() < 10:
            return 0.5
        else:
            raise ValueError(
                "Magnetic field ramp rate is not defined for temperatures above 10K."
            )

    def stabilize_at_magnetic_field(
        self,
        setpoint_magnetic_field: float,
        magnetic_field_ramp_rate: float | None = None,
    ) -> None:
        self.start_magnetic_field_sweep(
            setpoint_magnetic_field=setpoint_magnetic_field,
            magnetic_field_ramp_rate=magnetic_field_ramp_rate,
        )
        while not self.MagnetControl.stable:
            sleep(1)

    def stabilize_at_temperature(
        self,
        setpoint_temperature: float,
        user_temp_ramp_rate: float | None = None,
    ) -> None:
        temp_now = self.sample_stage_temperature()
        ramp_rate = self.check_temp_ramp_rate(user_temp_ramp_rate, setpoint_temperature)

        print(f"Stabilizing at {setpoint_temperature} K at {ramp_rate} K/min")
        self.TemperatureControl.start_proposed_mode(
            setpoint=setpoint_temperature,
            ramp=ramp_rate,
            mode="stabilize",
            start_temperature=temp_now,
        )
        while not self.TemperatureControl.stable:
            sleep(1)

    def ramp_temperature(self, start: float, stop: float) -> None:
        """Before sending other commands to the Kiutra, it is good practice
        to let the system complete the previous command. To ensure this,
        one should verify that the temperature is stable also at the end of this process."""

        self.stabilize_at_temperature(setpoint_temperature=start)

        rate = self.get_temp_ramp_rate(start, stop)
        print(f"Ramping to {stop} K at {rate} K/min")
        self.TemperatureControl.start_proposed_mode(
            setpoint=stop, ramp=rate, mode="ramp", start_temperature=start
        )

    def check_temp_ramp_rate(
        self, user_set_rate: float | None, setpoint_temperature: float
    ) -> float | None:
        temp_now = self.sample_stage_temperature()
        default_ramp_rate = self.get_temp_ramp_rate(temp_now, setpoint_temperature)

        if user_set_rate is not None:
            if user_set_rate >= default_ramp_rate:
                raise ValueError(
                    f"Set ramp rate exceeds reccommended value of {default_ramp_rate} K/min"
                )
            else:
                return user_set_rate
        else:
            return default_ramp_rate

    def get_temp_ramp_rate(self, temp_1: float, temp_2: float) -> float:
        min_temp = min(temp_1, temp_2)

        if min_temp <= 0.3:
            ramp_rate = 0.05
        elif min_temp <= 0.5:
            ramp_rate = 0.10
        elif min_temp <= 1.0:
            ramp_rate = 0.15
        elif min_temp <= 4.0:
            ramp_rate = 0.20
        elif min_temp <= 20.0:
            ramp_rate = 0.25
        else:
            raise ValueError(
                "Temperature ramp rate is not defined for temperatures above 20K."
            )

        return ramp_rate

    def check_temp_control(self) ->None:

        if self.TemperatureControl.stable:
            pass
        else:
            raise RuntimeError("Temperature control is not stable. Either abort command or reset temp control from the GUI.")