"""Sens des axes et échelle de puissance par défaut du firmware (essais hôte, sans moteur réel)."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ARDUINO = '''#pragma once
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
'''

PRINCIPAL = '''#include "motor_pwm.h"
#include <cassert>
unsigned values[40]={0};
#if ESP_ARDUINO_VERSION_MAJOR >= 3
#define CH(n) values[MOTOR_PINS[n]]
#else
#define CH(n) values[n]
#endif
int main(){MotorPWM c;assert(c.begin());
%s
}
'''


def executer(corps, *options):
    dossier = Path(__file__).resolve().parents[1]/'firmware/ScanAtlas_WiFi'
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d/'Arduino.h').write_text(ARDUINO)
        (d/'esp_arduino_version.h').write_text('#define ESP_ARDUINO_VERSION_MAJOR 2\n')
        (d/'main.cpp').write_text(PRINCIPAL % corps)
        subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', *options, '-I', str(d), '-I', str(dossier),
                        str(d/'main.cpp'), '-o', str(d/'test')], check=True, capture_output=True)
        subprocess.run([str(d/'test')], check=True, capture_output=True)


class AxesEtPuissanceTests(unittest.TestCase):
    def test_sway_inverse_par_defaut(self):
        # Sway positif = gauche : avec le signe par défaut (-1), FL et RR avancent, FR et RL reculent.
        executer('c.drive(0,100,0);assert(CH(0)==255&&CH(1)==0);assert(CH(2)==0&&CH(3)==255);'
                 'assert(CH(4)==0&&CH(5)==255);assert(CH(6)==255&&CH(7)==0);')

    def test_sway_normal_avec_signe_positif(self):
        executer('c.drive(0,100,0);assert(CH(0)==0&&CH(1)==255);assert(CH(2)==255&&CH(3)==0);',
                 '-DAXIS_SWAY_SIGN=1')

    def test_apply_suit_le_meme_sens_que_drive(self):
        executer('c.apply(STRAFE_L,100);assert(CH(0)==255&&CH(1)==0);assert(CH(2)==0&&CH(3)==255);c.apply(FORWARD,100);assert(CH(0)==255&&CH(1)==0);assert(CH(2)==255&&CH(3)==0);')

    def test_pleine_echelle_et_moitie(self):
        executer('c.drive(100,0,0);assert(CH(0)==255);c.drive(50,0,0);assert(CH(0)==128);c.drive(0,0,0);assert(CH(0)==0);')

    def test_seuil_de_demarrage(self):
        executer('c.drive(1,0,0);assert(CH(0)==52);c.drive(100,0,0);assert(CH(0)==255);c.drive(0,0,0);assert(CH(0)==0);',
                 '-DMOTOR_DUTY_MIN=50')

    def test_fonction_de_conversion(self):
        executer('assert(powerToDuty(0)==0&&powerToDuty(100)==255&&powerToDuty(-100)==-255&&powerToDuty(500)==255);')


if __name__ == '__main__':
    unittest.main()
