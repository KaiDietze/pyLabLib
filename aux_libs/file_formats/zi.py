"""
Files generated by the Zutich Instruments ziControl (old LabView version).
"""

from ...core.fileio import loadfile  #@UnresolvedImport

import os.path
import numpy as np


def load_spectr_file(path, result_format="xy"):
    """
    Load a single demod scope (demod samples vs. time) file.
    """
    data=loadfile.load(path)
    if data.shape[1]==7:
        del data.c[4]
        data.set_column_names(["Time","X","Y","Freq","AuxIn1","AuxIn2"])
        data["Time"]-=data["Time",0]
        if result_format=="comp":
            data.c.insert("X",data["X"]+1j*data["Y"],"C")
            del data.c[["X","Y"]]
        elif result_format!="xy":
            raise ValueError("unrecognized format: {}".format(result_format))
    else:
        raise ValueError("unexpected number of columns: {}".format(data.shape[1]))
    return data

def load_spectr_folder(path, result_format="xy"):
    """
    Load a folder containing demod scope files.

    Return a list of 6 elements (one pere demod), which are either ``None``, if there's not data for this demod, or contain that demod's trace.
    """
    data=[]
    for demod in range(1,7):
        file_path=os.path.join(path,"Freq{}.csv".format(demod))
        if os.path.exists(file_path):
            data.append(load_spectr_file(file_path,result_format=result_format))
        else:
            data.append(None)
    return data




def load_sweep_file(path, result_format="xy"):
    """
    Load a single sweep file (demod samples vs. drive frequency).
    """
    data=loadfile.load(path)
    if data.shape[1]==8:
        del data.c[4:]
        data.set_column_names(["Freq","R","Theta","Bandwidth"])
        data["Theta"]*=np.pi/180.
        if result_format=="comp":
            data.c.insert("R",data["R"]*np.exp(1j*data["Theta"]),"C")
        elif result_format=="xy":
            data.c.insert("R",data["R"]*np.cos(data["Theta"]),"X")
            data.c.insert("R",data["R"]*np.sin(data["Theta"]),"Y")
        else:
            raise ValueError("unrecognized format: {}".format(result_format))
        del data.c[["R","Theta"]]
    else:
        raise ValueError("unexpected number of columns: {}".format(data.shape[1]))
    return data

def load_sweep_folder(path, result_format="xy"):
    """
    Load a folder containing a demod sweep file.
    """
    return load_sweep_file(os.path.join(path,"Data.csv"),result_format=result_format)