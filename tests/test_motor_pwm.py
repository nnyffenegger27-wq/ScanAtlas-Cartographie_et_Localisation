"""Vérifications hôte du PWM : appels de sorties et profil, sans moteur réel."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class MotorPWMTests(unittest.TestCase):
    def test_pwm_stop_sens_et_versions_api(self):
        dossier=Path(__file__).resolve().parents[1]/'firmware/ScanAtlas_WiFi'
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            (d/'Arduino.h').write_text('''#pragma once
#include <algorithm>
using std::min;
#define OUTPUT 1
#define LOW 0
inline void pinMode(int,int){} inline void digitalWrite(int,int){}
extern unsigned values[40];
inline double ledcSetup(int,int,int){return 1;}
inline void ledcAttachPin(int,int){}
inline bool ledcAttach(int,int,int){return true;}
inline void ledcWrite(int n,unsigned p){values[n]=p;}
''')
            (d/'main.cpp').write_text('''#include "motor_pwm.h"
#include <cassert>
unsigned values[40]={0};
int main(){MotorPWM c;assert(c.begin());
unsigned n=0;assert(parseUsbRequest("SCAN 20",n)&&n==20);
assert(!parseUsbRequest("SCAN 21",n));assert(!parseUsbRequest("SCAN -1",n));
assert(!parseUsbRequest("SCAN 2 extra",n));assert(parseUsbRequest("SCAN 0",n)&&n==0);
c.apply(FORWARD,65);
for(int i=0;i<4;++i){
#if ESP_ARDUINO_VERSION_MAJOR >= 3
 assert(values[MOTOR_PINS[2*i]]==65);assert(values[MOTOR_PINS[2*i+1]]==0);
#else
 assert(values[2*i]==65);assert(values[2*i+1]==0);
#endif
}
c.apply(BACK,65);
for(int i=0;i<4;++i){
#if ESP_ARDUINO_VERSION_MAJOR >= 3
 assert(values[MOTOR_PINS[2*i]]==0);assert(values[MOTOR_PINS[2*i+1]]==65);
#else
 assert(values[2*i]==0);assert(values[2*i+1]==65);
#endif
}
c.stop();for(unsigned v:values)assert(v==0);
}
''')
            for version in (2,3):
                (d/'esp_arduino_version.h').write_text(f'#define ESP_ARDUINO_VERSION_MAJOR {version}\n')
                subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-I',str(d),'-I',str(dossier),str(d/'main.cpp'),'-o',str(d/'test')],check=True,capture_output=True)
                subprocess.run([str(d/'test')],check=True,capture_output=True)
