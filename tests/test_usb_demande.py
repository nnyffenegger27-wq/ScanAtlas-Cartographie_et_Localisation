import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from acquisition import capturer

class USBTests(unittest.TestCase):
    def test_requete_et_arret_csv_identique(self):
        angles=np.arange(359,-1,-1)
        flux=(''.join(f'{i},{a},1000,230,0,0\n' for i,a in enumerate(angles))+'\n').encode()
        envois=[]
        class Liaison:
            def __init__(self,*args,**kwargs):self.flux=flux
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def reset_input_buffer(self):pass
            def write(self,data):envois.append(data)
            @property
            def in_waiting(self):return len(self.flux)
            def read(self,n):
                data,self.flux=self.flux[:n],self.flux[n:];return data
        annuler=threading.Event()
        with patch.dict('sys.modules',{'serial':SimpleNamespace(Serial=Liaison)}),patch.object(annuler,'wait',return_value=False):
            scans=capturer('FAUX',115200,1,annuler,lambda t:None,demander_scan=True)
        self.assertEqual(envois,[b'SCAN 1\n',b'SCAN 0\n'])
        self.assertEqual(len(scans[0].mesures),360)
        np.testing.assert_array_equal(scans[0].mesures[:,0],angles)
