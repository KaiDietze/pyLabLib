"""
File wormats generated by the LabView code on the waveguide project.
"""


from io import open

from ...core.utils import string, funcargparse, files as file_utils
from ...core.fileio import loadfile
from ...core.dataproc import interpolate, filters, waveforms
from ...core.datatable.table import DataTable
from ...core.datatable.wrapping import wrap
import os.path

import numpy as np



##### .cam format (camera images) #####
def _read_cam_frame(f, skip=False):
    size=np.fromfile(f,"<u4",count=2)
    if len(size)==0 and file_utils.eof(f):
        raise StopIteration
    if len(size)<2:
        raise IOError("not enough cam data to read the frame size")
    w,h=size
    if not skip:
        data=np.fromfile(f,"<u2",count=w*h)
        if len(data)<w*h:
            raise IOError("not enough cam data to read the frame: {} pixels available instead of {}".format(len(data),w*h))
        return data.reshape((w,h))
    else:
        f.seek(w*h*2,1)
        return None
def iter_cam_frames(path, start=0, step=1):
    """
    Iterate of frames in a .cam datafile.

    Yield 2D array (one array per frame).
    Frames are loaded continuously, so the function is suitable for large files.
    """
    n=0
    with open(path,"rb") as f:
        while True:
            skip=not ((n>=start) and ((n-start)%step==0))
            try:
                data=_read_cam_frame(f,skip=skip)
            except StopIteration:
                break
            if not skip:
                yield data
            n+=1
def load_cam(path, same_size=True):
    """
    Load .cam datafile.

    Return list of 2D numpy arrays, one array per frame.
    If ``same_size==True``, raise error if different frames have different size.
    """
    frames=[]
    for f in iter_cam_frames(path):
        if frames and f.shape!=frames[0].shape:
            raise IOError("camera frame {} has a different size: {}x{} instead of {}x{}".format(len(frames),*(f.shape+frames[0].shape)))
        frames.append(f)
    return frames
def combine_cam_frames(path, func, init=None, start=0, step=1, max_frames=None, return_total=False):
    """
    Combine .cam frames using the function `func`.

    `func` takes 2 arguments (the accumulated result and a new frame) and returns the combined result.
    `init` is the inital result value; if ``init is None`` it is initialized to the first frame.
    If `max_frames` is not ``None``, it specifies the maximal number of frames to read.
    If ``return_total==True'``, return a tuple ``(result, n)'``, where `n` is the total number of frames.
    """
    n=0
    result=init
    for f in iter_cam_frames(path,start=start,step=step):
        if result is None:
            result=f
        else:
            result=func(result,f)
        n+=1
        if max_frames and n>=max_frames:
            break
    return (result,n) if return_total else result


class CamReader(object):
    """
    Reader class for .cam files.

    Allows transparent access to frames by reading them from the file on the fly (without loading the whole file).
    Supports determining length, indexing (only positive single-element indices) and iteration.

    Args:
        path(str): path to .cam file.
        same_size(bool): if ``True``, assume that all frames have the same size, which speeds up random access and obtaining number of frames;
            otherwise, the first time the length is determined or a large-index frame is accessed can take a long time (all subsequent calls are faster).
    """
    def __init__(self, path, same_size=False):
        object.__init__(self)
        self.path=path
        self.frame_offsets=[0]
        self.frames_num=None
        self.same_size=same_size

    def _read_frame_at(self, offset):
        with open(self.path,"rb") as f:
            f.seek(offset)
            return _read_cam_frame(f)
    def _read_next_frame(self, f, skip=False):
        data=_read_cam_frame(f,skip=skip)
        self.frame_offsets.append(f.tell())
        return data
    def _read_frame(self, idx):
        idx=int(idx)
        if self.same_size:
            if len(self.frame_offsets)==1:
                with open(self.path,"rb") as f:
                    self._read_next_frame(f,skip=True)
            offset=self.frame_offsets[1]*idx
            return self._read_frame_at(offset)
        else:
            if idx<len(self.frame_offsets):
                return self._read_frame_at(self.frame_offsets[idx])
            next_idx=len(self.frame_offsets)
            offset=self.frame_offsets[-1]
            with open(self.path,"rb") as f:
                f.seek(offset)
                while next_idx<=idx:
                    data=self._read_next_frame(f,next_idx<idx)
                    next_idx+=1
            return data

    def _fill_offsets(self):
        if self.frames_num is not None:
            return
        if self.same_size:
            file_size=os.path.getsize(self.path)
            if file_size==0:
                self.frames_num=0
            else:
                with open(self.path,"rb") as f:
                    self._read_next_frame(f,skip=True)
                if file_size%self.frame_offsets[1]:
                    raise IOError("File size {} is not a multile of single frame size {}".format(file_size,self.frame_offsets[1]))
                self.frames_num=file_size//self.frame_offsets[1]
        else:
            offset=self.frame_offsets[-1]
            try:
                with open(self.path,"rb") as f:
                    f.seek(offset)
                    while True:
                        self._read_next_frame(f,skip=True)
            except StopIteration:
                pass
            self.frames_num=len(self.frame_offsets)-1
    
    def size(self):
        """Get the total number of frames"""
        self._fill_offsets()
        return self.frames_num
    __len__=size

    def __getitem__(self, idx):
        try:
            return self._read_frame(idx)
        except StopIteration:
            raise IndexError("index {} is out of range".format(idx))
    def get_data(self, idx):
        return self[idx]
    def __iter__(self):
        return self.iterrange()
    def iterrange(self, *args):
        """
        iterrange([start,] stop[, step])

        Iterate over frames starting with `start` ending at `stop` (``None`` means until the end of file) with the given `step`.
        """
        start,stop,step=0,None,1
        if len(args)==1:
            stop,=args
        elif len(args)==2:
            start,stop=args
        elif len(args)==3:
            start,stop,step=args
        try:
            n=start
            while True:
                yield self._read_frame(n)
                n+=step
                if stop is not None and n>=stop:
                    break
        except StopIteration:
            pass


def save_cam(frames, path, append=True):
    """
    Save `frames` into a .cam datafile.

    If ``append==False``, clear the file before writing the frames.
    """
    mode="ab" if append else "wb"
    with open(path,mode) as f:
        for fr in frames:
            np.array(fr.shape).astype("<u4").tofile(f)
            fr.astype("<u2").tofile(f)



##### _info.txt format (file info) #####
def load_info(path):
    """
    Load the info file (ends with ``"_info.txt"``).

    Return information as a dictionary ``{name: value}``, where `value` is a list (single-element list for a scalar property).
    """
    nextline_markers=["locking scheme", "channels"]
    lines=[]
    with open(path) as f:
        for ln in f.readlines():
            ln=ln.strip()
            while ln.endswith(":"):
                ln=ln[:-1]
            items=[i.strip() for i in ln.split("\t")]
            items=[i for i in items if i]
            if items:
                lines.append(items)
    info_dict={}
    n=0
    while n<len(lines):
        ln=lines[n]
        if len(ln)==1 and ln[0].lower() in nextline_markers:
            key=ln[0].lower()
            if len(lines)==n+1:
                raise IOError("key line {} doesn't have a following value line".format(ln[0]))
            value=[string.from_string(i) for i in lines[n+1]]
            n+=1
        elif len(ln)>=2:
            key=ln[0].lower()
            value=[string.from_string(i) for i in ln[1:]]
        else:
            raise IOError("unusual line format: {}".format(ln))
        if key in info_dict:
            raise IOError("duplicate key: {}".format(key))
        info_dict[key]=value
        n+=1
    return info_dict


def _filter_channel_name(name):
    return name.replace(" ","").replace("-","_")
def load_sweep(prefix, force_info=True):
    """
    Load binary sweep located at ``prefix+".dat"`` with an associated info file located at ``prefix+"_info.txt"``.

    Return tuple ``(table, info)``, where `table` is the data table, and `info` is the info dictionary (see :func:`load_info`).
    If ``force_info==True``, raise an error if the info file is missing.
    The columns for `table` are extracted from the info file. If it is missing or the channels info is not in the file, `table` has a single column.
    """
    info_path=prefix+"_info.txt"
    if os.path.exists(info_path):
        info_dict=load_info(info_path)
    elif force_info:
        raise IOError("info file {} doesn't exits".format(info_path))
    else:
        info_dict={}
    if "channels" in info_dict:
        info_dict["channels"]=[_filter_channel_name(ch) for ch in info_dict["channels"]]
        channels=info_dict["channels"]
    else:
        channels=[]
    data_path=prefix+".dat"
    data=loadfile.load(data_path,"bin",dtype="<f8",columns=channels)
    return data,info_dict


##### Normalizing sweep (frequency and column data) #####
def cut_outliers(sweep, jump_size, length, padding=0, x_column=None, ignore_last=0):
    xs=waveforms.get_x_column(sweep,x_column=x_column)
    dxs=xs[1:]-xs[:-1]
    jumps=abs(dxs)>jump_size
    jump_locs=np.append(jumps.nonzero()[0],[len(xs)-1])
    prev_jump=-1
    include=np.ones(len(xs)).astype("bool")
    for jl in jump_locs:
        if jl>len(include)-ignore_last:
            break
        if jl-prev_jump<length:
            start=max(prev_jump+1-padding,0)
            end=min(jl+1+padding,len(include))
            include[start:end]=False
        prev_jump=jl
    return wrap(sweep).t[include,:].copy()

def trim_jumps(sweep, jump_size, trim=1, x_column=None):
    if not isinstance(trim,(list,tuple)):
        trim=trim,trim
    xs=waveforms.get_x_column(sweep,x_column=x_column)
    dxs=xs[1:]-xs[:-1]
    jumps=abs(dxs)>jump_size
    jump_locs=jumps.nonzero()[0]
    include=np.ones(len(xs)).astype("bool")
    for jl in jump_locs:
        start=max(jl-trim[0]+1,0)
        end=min(jl+1+trim[1],len(include))
        include[start:end]=False
    return wrap(sweep).t[include,:].copy()

def prepare_sweep_frequency(sweep, allowed_frequency_jump=None, ascending_frequency=True, rescale=True):
    """
    Clean up the sweep frequency data (exclude jumps and rescale in Hz).
    
    Find the longest continuous chunk with frequency steps within `allowed_frequency_jump' range (by default, it is ``(-5*mfs,infty)``, where ``mfs`` is the median frequency step).
    If ``ascending_frequency==True``, sort the data so that frequency is in the ascending order.
    If ``rescale==True``, rescale frequency in Hz.
    """
    if rescale:
        sweep["Wavemeter"]*=1E12
    if len(sweep)>1:
        fs=sweep["Wavemeter"]
        dfs=fs[1:]-fs[:-1]
        fdir=1. if np.sum(dfs>0)>len(dfs)//2 else -1.
        valid_dfs=(dfs*fdir)>0
        if allowed_frequency_jump=="auto":
            mfs=np.median(dfs[valid_dfs])
            maxfs=fdir*np.max(dfs[valid_dfs]*fdir)
            allowed_frequency_jump=(-10*mfs, 1.1*maxfs )
        if allowed_frequency_jump is not None:
            bins=filters.collect_into_bins(fs,allowed_frequency_jump,preserve_order=True,to_return="index")
            max_bin=sorted(bins, key=lambda b: b[1]-b[0])[-1]
            sweep=sweep.t[max_bin[0]:max_bin[1],:]
        if ascending_frequency:
            sweep=sweep.sort_by("Wavemeter")
    return sweep
def interpolate_sweep(sweep, columns, frequency_step, rng=None, frequency_column="Wavemeter"):
    """
    Interpolate sweep data over a regular frequency grid with the spacing `frequency_step`.
    """
    rng_min,rng_max=rng or (None,None)
    rng_min=sweep[frequency_column].min() if (rng_min is None) else rng_min
    rng_max=sweep[frequency_column].max() if (rng_max is None) else rng_max
    start_freq=(rng_min//frequency_step)*frequency_step
    stop_freq=(rng_max//frequency_step)*frequency_step
    columns=[funcargparse.as_sequence(c,2) for c in columns]
    freqs=np.arange(start_freq,stop_freq+frequency_step/2.,frequency_step)
    data=[interpolate.interpolate1D(sweep[frequency_column],sweep[src],fill_values="bounds")(freqs) for src,_ in columns]
    return DataTable([freqs]+data,["Frequency"]+[dst for _,dst in columns])



rep_suffix_patt="_rep_{:03d}"
def load_prepared_sweeps(prefix, reps, min_sweep_length=1, **add_info):
    """
    Load sweeps with the given `prefix` and `reps` and normalize their frequency axes.

    Return list of tuples ``(sweep, info)``. `add_info` is added to the `info` dictionary (`rep` index is added automatically).
    `min_sweep_length` specifies the minimal sweep length (after frequecy normalization) to be included in the list.
    """
    sweeps=[]
    if reps:
        for rep in reps:
            sweep_name=prefix+rep_suffix_patt.format(rep)
            sweeps+=load_prepared_sweeps(sweep_name,[],min_sweep_length=min_sweep_length,rep=rep,**add_info)
    else:
        try:
            sweep,info=load_sweep(prefix,force_info=True)
            sweep=prepare_sweep_frequency(sweep)
            if len(sweep)>=min_sweep_length:
                info["rep"]=0
                info.update(add_info)
                sweeps.append((sweep,info))
        except IOError:
            pass
    return sweeps