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
#if ESP_ARDUINO_VERSION_MAJOR >= 3
#define CH(n) values[MOTOR_PINS[n]]
#else
#define CH(n) values[n]
#endif
// Commande combinée : FL FR RL RR = moteurs M1..M4, canaux A (avant) puis B (arrière).
c.drive(60,0,0);for(int i=0;i<4;++i){assert(CH(2*i)==60);assert(CH(2*i+1)==0);}
c.drive(0,50,0);   // gauche : FL et RR reculent, FR et RL avancent
assert(CH(0)==0&&CH(1)==50);assert(CH(2)==50&&CH(3)==0);assert(CH(4)==50&&CH(5)==0);assert(CH(6)==0&&CH(7)==50);
c.drive(0,0,100);  // rotation à gauche : côté gauche recule, côté droit avance
assert(CH(1)==100&&CH(0)==0);assert(CH(2)==100&&CH(3)==0);assert(CH(5)==100&&CH(4)==0);assert(CH(6)==100&&CH(7)==0);
c.drive(100,100,0);  // saturation : FL et RR s'annulent, FR et RL à 100
assert(CH(0)==0&&CH(1)==0);assert(CH(2)==100);assert(CH(4)==100);assert(CH(6)==0&&CH(7)==0);
c.drive(0,0,0);for(unsigned v:values)assert(v==0);
c.drive(60,0,0);c.apply(STOP,65);for(unsigned v:values)assert(v==0);
}
''')
            for version in (2,3):
                (d/'esp_arduino_version.h').write_text(f'#define ESP_ARDUINO_VERSION_MAJOR {version}\n')
                subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-DAXIS_SWAY_SIGN=1','-DMOTOR_DUTY_MAX=100','-I',str(d),'-I',str(dossier),str(d/'main.cpp'),'-o',str(d/'test')],check=True,capture_output=True)
                subprocess.run([str(d/'test')],check=True,capture_output=True)
