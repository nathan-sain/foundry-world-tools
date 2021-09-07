import os
import sys
import json
import logging
import filecmp
import re
import errno
import shutil
import stat
import random
import string
import jsonlines
import urllib.request
import urllib.parse
from pathlib import Path
from itertools import tee,chain
from tempfile import gettempdir
from collections import UserDict
from types import SimpleNamespace
from contextlib import AbstractContextManager
from pathlib import Path as _Path_, _windows_flavour, _posix_flavour

__version__ = '0.4.5'
LOG_LEVELS = ["ERROR","INFO","WARNING","DEBUG"]

def find_list_dups(c):
        '''sort/tee/izip'''
        a, b = tee(sorted(c))
        next(b, None)
        r = None
        for k, g in zip(a, b):
            if k != g: continue
            if k != r:
                yield k
                r = k

#XXX add to FWTFileWriter and FWTFile
def cpSecPerm(src,target):
    st = os.stat(src)
    if 'chown' in dir(os):
        os.chown(target, st.st_uid, st.st_gid)
    shutil.copymode(src, target)

def find_next_avaliable_path(output_path):
    output_path = Path(output_path)
    n = int(output_path.suffix[1:])
    while output_path.exists():
        n += 1
        output_path = output_path.with_suffix(f".{n}")
    return output_path

def find_foundry_user_dir(search_path):
    try:
        search_path = Path(search_path)
        fvtt_options = Path(
            next(f for p in (search_path,*search_path.parents)
                for f in p.glob("Config/*.json")
                if f.name == "options.json")
            )   
        data_path = json.load(fvtt_options.open())['dataPath']
        foundry_user_dir = Path(data_path) / "Data"
    except StopIteration:
        foundry_user_dir = False
    return foundry_user_dir

def get_relative_to(path, rs):
    logging.debug(f"get_relative_to: got base {path} and rel {rs}")
    pobj = Path(path)
    path = Path(path)
    if ".." in str(rs):
        rp = path / rs
        for e in rp.relative_to(path).parts:
            if e == '..':
                pobj = pobj.parent
            else:
                pobj = pobj / e
    else:
        pobj = path / rs
    logging.debug(f"get_relative_to: new rel path {pobj}")
    return Path(pobj)


def reinit_fwtpath(fwtpath,newpath):
    fwtpath._drv = newpath._drv
    fwtpath._root = newpath._root
    fwtpath._parts = newpath._parts
    fwtpath._str = str(newpath)

def resolve_fvtt_path(fwtpath,
                        path,
                        foundry_user_dir=False, 
                        exists=True,
                        check_for_project=True,
                        require_project=False,
                    ):
    """
    Resolve symlinks and relative paths into foundry user dir paths
    """
    if not fwtpath.is_absolute():
        cwd = os.environ.get('PWD',os.getcwd())
        temp_path = get_relative_to(_Path_(cwd),path)     
        path = temp_path.as_posix()
        reinit_fwtpath(fwtpath,temp_path)
        logging.debug(f"Detected relative path. Translated to {path}")
    if foundry_user_dir:
        fwtpath._fwt_fud = _Path_(foundry_user_dir)
    elif fwtpath.foundry_user_dir:
        fwtpath._fwt_fud = _Path_(fwtpath.foundry_user_dir)
    else:
        fwtpath._fwt_fud = find_foundry_user_dir(path)
    if not fwtpath._fwt_fud or not fwtpath._fwt_fud.exists():
        raise FUDNotFoundError(f"{path}: no foundry user data directory found")
    if fwtpath.as_posix().startswith(fwtpath._fwt_fud.as_posix()):
        fwtpath._fwt_rtp = fwtpath.relative_to(fwtpath._fwt_fud)
        symlink = False
    else:
        logging.debug("Path is outside Foundry user directory. Possible symlink")
        symlink = True
        fwtpath._fwt_rtp = None
    if check_for_project or symlink:
        try:
            manafest = next(f for d in (fwtpath,*fwtpath.parents) for f in d.glob("*.json")
                            if f.name in fwtpath.project_manafests)
            fwtpath.project_type = f"{manafest.stem}"
            fwtpath.project_name = json.loads(manafest.read_text())["name"]
            fwtpath.is_project = True
            if not manafest.parent.name == fwtpath.project_name:
                logging.warning("project directory and name are different")
            if symlink:                
                fwtpath._fwt_rpd = _Path_(f"{fwtpath.project_type}s/{fwtpath.project_name}")
                if fwtpath != manafest.parent:
                    fwtpath._fwt_rtp = _Path_(fwtpath._fwt_rpd / fwtpath.relative_to(manafest.parent))
                else: fwtpath._fwt_rtp = fwtpath._fwt_rpd
            else:
                fwtpath._fwt_rpd = manafest.parent.relative_to(fwtpath._fwt_fud)
            fwtpath.manafest = fwtpath._fwt_fud / fwtpath._fwt_rpd / manafest.name
        except StopIteration:
            if require_project or symlink:
                raise FWTPathError(
                    f"{path} is not part of a Foundry project"
                    f" in the {fwtpath._fwt_fud} directory")
            else:
                fwtpath.is_project = False
                if len(fwtpath._fwt_rtp.parents) >= 3:
                    fwtpath._fwt_rpd = list(fwtpath._fwt_rtp.parents)[-3]
                else:
                    fwtpath._fwt_rpd = fwtpath._fwt_rtp
    reinit_fwtpath(fwtpath, fwtpath._fwt_fud / fwtpath._fwt_rtp)


class FWTConfigNoDataDir(Exception):
    pass

class FWTConfig(UserDict):    
    """An object for loading and saving JSON config files"""
    def __init__(self,file_path,mkconfig=False,*args,**kwargs):
        super().__init__(*args,**kwargs)
        config_file = Path(file_path)
        if '~' in str(file_path):
            h = config_file
            self.config_file = Path(h.as_posix().replace('~',h.home().as_posix()))
        else:
            self.config_file = config_file
        if self.config_file.exists():
            if self.config_file.stat().st_size > 1:
                self.load()
                logging.debug(f"Loaded Config File. Config Data are: \n{json.dumps(self.data, indent=4, sort_keys=True)}")
            else:
                self.create_config()
        elif mkconfig:
            self.create_config()
        else:
            raise FWTFileError("Config file does not exist")
        self.setup()

    def setup(self):
        fvtt_user_dir = self.data.get('dataDir',None)
        if not fvtt_user_dir:
            search_path = Path(os.environ.get('PWD',os.getcwd()))
            fvtt_user_dir = find_foundry_user_dir(search_path)
        if fvtt_user_dir:
            FWTPath.foundry_user_dir = fvtt_user_dir
        else:
            raise FWTConfigNoDataDir("unable to determine fvtt_data_dir")

    def load(self):
        with self.config_file.open("r+t",encoding='utf-8') as cf:
            try:
                config_data = json.load(cf)
                self.data.update(config_data)
                logging.debug(f"Loaded configuration file {self.config_file}")
            except json.JSONDecodeError as e:
                logging.error(f"unable to parse config\n{e}")
                self.data = {"error":f"{e}"}
    
    def save(self):
        with FWTFileWriter(self.config_file) as cf:
            config_json = json.dumps(self.data, indent=4, sort_keys=True)
            cf.write_fd.write(config_json)

    def create_config(self):
        from pkg_resources import resource_string as resource_bytes
        logging.debug(f"create_config: {self.config_file}")
        presets_json = resource_bytes('foundryWorldTools','presets.json').decode('utf-8')
        self.data.update(json.loads(presets_json))
        if not self.config_file.parent.exists():
            self.config_file.parent.mkdir()   
        self.save()

class FWTPathError(Exception):
    pass

class FWTPathNoProjectError(Exception):
    pass

class FUDNotFoundError(Exception):
    pass

class FWTFileError(Exception):
    pass

class FWTFileManager:
    """manage project files and update foundry db when file paths change"""
    def __init__(self,project_dir,trash_dir="trash"):
        logging.debug(f"FWT_FileManager.__init__: Creating object with "
            f"project dir {project_dir}")
        self.project_dir = FWTPath(project_dir,require_project=True).to_fpd()
        if trash_dir:
            if not _Path_(trash_dir).is_absolute():
                trash_dir = self.project_dir / trash_dir
            self.trash_dir = find_next_avaliable_path(
                trash_dir / "session.0")
            self.trash_dir.mkdir(parents=True,exist_ok=True)
        else:
            self.trash_dir = None
        self._dir_exclusions = set()
        self._dir_exclusions.add(self.trash_dir.parent.as_posix() + "*")
        self._dir_exclusions.add((self.project_dir / "data").as_posix())
        self._dir_exclusions.add((self.project_dir / "packs").as_posix())
        self.__file_extensions = set()
        self._files = []
        self.rewrite_names_pattern = None
        self.remove_patterns = []
        self.replace_patterns = []
        self._dbs = FWTProjectDb(self.project_dir,FWTTextDb,self.trash_dir)

    @property
    def project_dir(self):
        return self._project_dir

    @project_dir.setter
    def project_dir(self,project_dir):
        project_dir = FWTPath(project_dir)
        if not project_dir.is_absolute() or not project_dir.exists():
            raise FWTFileError(f"invalid project dir {project_dir}")
        self._project_dir = project_dir


    @property
    def file_extensions(self):
        return frozenset(self.__file_extensions)
    
    def add_file_extensions(self,e):
        if type(e) == str:
            self.__file_extensions.add(e)
        if type(e) in (tuple,list,set,frozenset):
            for i in e: self.__file_extensions.add(i)

    @property
    def name(self):
        return self.project_dir.name

    @property
    def manafest(self):
        if self.project_dir.is_project:
            return json.loads(self.project_dir.manafest.read_text())

    @manafest.setter
    def manafest(self,update):
        if self.project_dir.is_project:
            temp_manafest = self.manafest
            temp_manafest.update(update)
            with FWTFileWriter(self.project_dir.manafest,trash_dir=self.trash_dir) as f:
                f.write(json.dumps(temp_manafest))
            return temp_manafest
            
    def add_exclude_dir(self,dir):
        self._dir_exclusions.add(dir)

    def scan(self):
        scanner = FWTScan(self.project_dir)
        if len(self.file_extensions):
            ext_filter = FileExtensionsFilter()
            for e in self.file_extensions: ext_filter.add_match(e)
            scanner.add_filter(ext_filter)
        if len(self._dir_exclusions):
            dir_filter = DirNamesFilter()
            for d in self._dir_exclusions: dir_filter.add_match(d)
            scanner.add_filter(dir_filter) 
        for f in scanner:
            self.add_file(f)


    def generate_rewrite_queue(self,lower=False):
        logging.info("FWT_FileManager.generate_rewrite_queue starting")
        rewrite_queue = {}
        for f in self._files:
            if self.remove_patterns or self.replace_patterns or lower:
                rel_path = f.new_path.as_rpp() if f.new_path else f.path.as_rpp()
                logging.debug(f"rewrite file name starts as {rel_path}")
                rel_path_parts = rel_path.split('/')
                new_rel_path = []
                for e in rel_path_parts:
                    for pat in self.remove_patterns:
                        e = pat.sub('',e)
                    for pat,rep in self.replace_patterns:
                        e = pat.sub(rep,e)
                    if lower:
                        e = e.lower()
                    new_rel_path.append(e)
                rel_path = '/'.join(new_rel_path)
                logging.debug(f"rewrite filename to {rel_path}")
                f.new_path = f.path.to_fpd() / rel_path
            if f.new_path:
                logging.debug(f"fm_generate_rewrite_queue: " 
                f"{f.path.as_rtp()} -> {f.new_path.as_rtp()}")
                rewrite_queue.update({f.path.as_rtp():f.new_path.as_rtp()})
        self.rewrite_queue = rewrite_queue

    def process_rewrite_queue(self,quote_find=True):
        """do db rewrites"""
        if(len(self.rewrite_queue)):
            self.db_replace(batch=self.rewrite_queue,quote_find=quote_find)

    def process_file_queue(self):
        """do file renames and deletions"""
        for f in self._files:
            if f.new_path and f.keep_src:
                f.copy()
            elif f.new_path:
                f.rename()

    def add_remove_pattern(self,pattern):
        re_pattern = re.compile(pattern)
        self.remove_patterns.append(re_pattern)

    def add_replace_pattern(self,pattern_set):
        #pattern,replacement = [e for e in pattern_set.split("/")][1:3]
        _, p, r, o = [e for e in re.split(r'(?<![^\\]\\)/',pattern_set)]
        re_pattern = re.compile(p)
        self.replace_patterns.append((re_pattern,r))
    
    def add_file(self,path):
        file = FWTFile(path,self.trash_dir)
        self._files.append(file)
        return file

    def db_replace(self,batch,quote_find=False):
        self.files_replace(
                            (self.project_dir.manafest,
                            *self.project_dir.glob("*/*db")),
                            batch,quote_find
                        )

    def files_replace(self,files,batch,quote_find=False):
        for file in files:
            logging.debug(f'opening db {file} for rewrite')

            with FWTFileWriter(file,read_fd=True,trash_dir=self.trash_dir) as f:
                for idx,line in enumerate(f.read_fd):
                    for find,replace in batch.items():
                        if type(find) == str: 
                            if quote_find: 
                                find,replace = f'"{find}"',f'"{replace}"'
                            line = line.replace(find,replace)
                        elif type(find) == re.Pattern:
                            line = find.sub(replace,line)
                        else:
                            raise ValueError("invalid member or rewrite queue")
                    f.write_fd.write(line)

    def find_remote_assets(self,src):
        src = FWTPath(src)
        remote_assets=set()
        dbs = FWTProjectDb(self.project_dir,driver=FWTTextDb)
        path_re = re.compile(r'"img":"(?P<path>'+src.as_rpd()+'[^"]*)"')
        for db in dbs:
            for obj in db:
                for a in path_re.findall(obj):
                    if a:
                        remote_assets.add(a)
        self._files = [FWTFile(src._fwt_fud / path,keep_src=True) for path in remote_assets]
        for f in self._files:
            np = f.path.as_rtp().replace(f.path.as_rpd(),self.project_dir.as_rpd())
            f.new_path = np
        
    def rename_world(self,dst,keep_src=False):
        dst = FWTPath(dst,exists=False)
        if dst.exists():
            raise FWTFileError("Cannot rename world using exiting directory")
        manafest_rpd = f"{self.project_dir.project_type}s/{self.project_dir.project_name}"
        dir_rewrite_match = re.compile(f'"{manafest_rpd}/([^"]+)"')
        dir_queue = {dir_rewrite_match:f'"{dst.as_rpd()}/\\1"'}
        name_rewrite_match = re.compile(re.escape(f'"{self.project_dir.project_name}"'))
        name_queue = {name_rewrite_match:f'"{dst.name}"'}

        if keep_src:
            shutil.copytree(self.project_dir,dst)
        else:
            os.renames(self.project_dir,dst)
        new_project = FWTFileManager(dst)
        new_project.files_replace([new_project.project_dir.manafest,],
                    {**dir_queue,**name_queue})
        new_project.db_replace(batch=dir_queue)

class FWTSetManager(FWTFileManager):
    """An object for managing duplicate assets"""
    def __init__(self,project_dir,detect_method=None,trash_dir="trash"):
        super().__init__(project_dir,trash_dir)
        self.preferred_patterns = []
        self.rewrite_queue = {}
        self.sets = {}
        if detect_method:
            self.detect_method = detect_method

    def add_preferred_pattern(self,pp):
        self.preferred_patterns.append(pp)

    @property
    def detect_method(self):
        return self._detect_method
    
    @detect_method.setter
    def detect_method(self,method):
        if method == "bycontent": 
            self._detect_method = "bycontent"
        elif method == "byname": 
            self._detect_method = "byname"
        else:
            raise ValueError("method must be bycontent or byname, got "
            f"{method}")
   
    def scan(self):
        scanner = FWTScan(self.project_dir)
        if len(self.file_extensions):
            ext_filter = FileExtensionsFilter()
            for e in self.file_extensions: ext_filter.add_match(e)
            scanner.add_filter(ext_filter)
        if len(self._dir_exclusions):
            dir_filter = DirNamesFilter()
            for d in self._dir_exclusions: dir_filter.add_match(d)
            scanner.add_filter(dir_filter) 
        for match in scanner:
            if self._detect_method == "bycontent":
                with match.open('rb') as f:
                    id = hash(f.read(4096))
                    if id == 0: continue # empty file
                while not self.add_to_set(id,match):
                    id += 1
            elif self._detect_method == "byname":
                id = (match.parent / match.stem).as_posix()
                self.add_to_set(id,match)

        single_sets = [k for k,v in self.sets.items() if len(v) < 2]
        for k in single_sets:
            del self.sets[k]
        
    def add_to_set(self,id,f):
        set = self.sets.get(id,FWTSet(id,trash_dir=self.trash_dir))
        if not set.files:
            self.sets[id] = set
            return set.add_file(f)
        elif (self._detect_method == "bycontent" and
              filecmp.cmp(f, set._files[0].path,shallow=False)):
            return set.add_file(f)
        elif self._detect_method == "byname":
            return set.add_file(f)
        else:
            return False


    def process_file_queue(self):
        """do file renames"""   
        for fwtset in self.sets.values():
            fwtset.preferred.rename()
            for f in fwtset.files:
                f.trash()

    def set_preferred_on_all(self):
        logging.info("FWT_SetManager.set_preferred_on_all: starting")
        for s in self.sets.values():
            for pattern in self.preferred_patterns:
                pattern = pattern.replace('<project_dir>',s.files[0].path.as_fpd())
                if s.choose_preferred(match=pattern):
                    logging.debug(f"set prefered with {pattern}")
                    break
            if not s.preferred:
                logging.debug(f"set prefered file to set item 0")
                s.choose_preferred(i=0)

    def generate_rewrite_queue(self):
        logging.info("FWT_SetManager.generate_rewrite_queue: starting")
        rewrite_queue = {}
        for fwtset in self.sets.values():
            rewrite_queue.update(fwtset.rewrite_data)
        self.rewrite_queue = rewrite_queue

class FWTPath(_Path_):
    """
    interface for representing paths in foundry assets.
    provides checks to ensure files are within foundry user data directory.
    api:
    - as_rtp() - posix string of target path relative to foundry data dir
    - to_rtp() - Path object of above
    - as_ftp() - posix string of target absolute path from fs root
    - to_ftp() - Path object of above
    - as_rpp() - posix string of target path relative to project path
    - as_rpd() - posix string of path to project root from foundry data dir
    - to_rpd() - Path object of above
    - as_fpd() - posix string of project absolute path from fs root
    - to_rpd() - Path object of above
    """
    #XXX! Figure out how to have a path_dir
    _flavour = _windows_flavour if os.name == 'nt' else _posix_flavour
    foundry_user_dir = None
    project_manafests = {"world.json", "module.json"}
    def __init__(self, path, 
                foundry_user_dir=False, 
                exists=True,
                check_for_project=True,
                require_project=False,
                ):
        self.orig_path = path
        self._fwt_fud = None
        self._fwt_rpd = None
        self._fwt_rtp = None
        self.is_project = False
        self.manafest = None
        self.project_name = ""
        self.project_type = ""
        resolve_fvtt_path(self,path)
        test_ftp = self._fwt_fud / self._fwt_rtp
        if not test_ftp.exists() and exists:
            raise FWTPathError(f"Requested path {test_ftp} does not exist!")



    def is_project_dir(self):
        if self.is_project:
            return self.as_fpd() == self.as_ftp()

    def as_rpd(self):
        return self._fwt_rpd.as_posix()

    def to_rpd(self):
        return self._fwt_rpd

    def as_rtp(self):
        return self._fwt_rtp.as_posix()

    def to_rtp(self):
        return self._fwt_rtp

    def to_fpd(self):
        return FWTPath(self._fwt_fud / self._fwt_rpd)

    def as_fpd(self):
        return self.to_fpd().as_posix()

    def to_ftp(self):
        return FWTPath(self._fwt_fud / self._fwt_rtp)

    def as_ftp(self):
        return self.to_ftp().as_posix()
    
    def as_rpp(self):
        return self.to_ftp().relative_to(self.to_fpd()).as_posix()

    def iterdir(self):
        return map(FWTPath, super().iterdir())

    def to_abs(self):
        return FWTPath(self.absolute())


class FWTFile:
    """interface for changing files"""

    def __init__(self, path, trash_dir=None, keep_src=False):
        self.path = FWTPath(path)        
        self.new_path = False
        self.trash_path = False
        self.locked = False
        if trash_dir:
            trash_dir = Path(trash_dir)
            if trash_dir.is_absolute():
                self.trash_dir = trash_dir
            else:
                self.trash_dir = self.path.to_fpd / trash_dir
        else:
            self.trash_dir = None
        self.keep_src = keep_src

    @property
    def path(self):
        return self.__path

    @path.setter
    def path(self,path):
        self.__path = FWTPath(path)

    @property
    def new_path(self):
        return self.__new_path

    @new_path.setter
    def new_path(self, new_path):
        if new_path == False:
            self.__new_path = False
            return True
        new_path = FWTPath(new_path, exists=False)
        if new_path.exists():
            if self.path.samefile(new_path):
                logging.warning("New path is the same as path, ignoring")
                return False
            if new_path.is_dir() and not self.path.is_dir():
                logging.debug("new path is dir and path is target updating "
                              f"new path to {new_path}")
                return self.__setattr__('new_path',new_path / self.path.name)
        self.__new_path = new_path
        return True

    def rename(self):
        if self.new_path:
            if self.keep_src:
                logging.debug("rename:keep_src requested using copy instead")
                return self.copy()
            if self.new_path.exists():
                raise FWTPathError(f"Can't rename file {self.path}\n"
                                    f"Target {self.new_path} exists!")
            os.renames(self.path,self.new_path)
            self.old_path = self.path
            self.path = self.new_path
            self.new_path = False
            logging.debug(
                f"rename:completed rename of {self.old_path} -> {self.path}")
            return True
        return False

    def copy(self, overwrite=False):
        if not self.new_path:
            return False
        if self.new_path.exists() and not overwrite:
            raise FWTPathError(
                f"Can't copy file {self.path}\nTarget {self.new_path} exists!")
        os.makedirs(self.new_path.parent, exist_ok=True)
        shutil.copy2(self.path, self.new_path)
        self.copy_of = self.path
        self.path = self.new_path
        self.new_path = False
        logging.debug(f"copy:completed copy of {self.copy_of} -> {self.path}")
        return True

    def trash(self):
        if self.trash_dir:
            world_path = self.path.to_ftp().relative_to(self.path.to_fpd())
            self.new_path = FWTPath(self.trash_dir / world_path,exists=False)
            return self.rename()
        else:
            self.path.unlink()
            self.new_path = False
            logging.debug("trash: trash not set unlinking file")
            return True

    #XXX delete this method?
    def as_rewrite(self,new_path=True,copy_of=False,old_path=False):
        if new_path and self.new_path:
            rd = {self.path.as_rtp(): self.new_path.as_rtp()}
        elif copy_of and self.copy_of:
            rd = {self.copy_of.as_rtp(): self.path.as_rtp()}
        elif old_path and self.old_path:
            rd = {self.old_path.as_rtp(): self.path.as_rtp()}
        logging.debug("as_rewrite: %s -> %s" % rd.items()[0])
        return rd

    def __repr__(self):
        return self.__str__()

    def __cmp__(self,other):
        return self.__str__() == other.__str__()

    def __str__(self):
        return f"{self.path.as_ftp()}"

class FWTSet:
    """
    An object that contains a set of files representing the same asset 
    and methods for choosing a preferred file and removing the rest
    """
    def __init__(self,id=None,trash_dir=None):
        self.id = id
        self._files = []
        self._preferred = None
        self.trash_dir = trash_dir

    @property
    def rewrite_data(self):
        data = {}
        if self._preferred.new_path:
            db_new_path = self._preferred.new_path.as_rtp()
            data.update({self._preferred.path.as_rtp():db_new_path})
        else:
            db_new_path = self._preferred.path.as_rtp()
        for f in self._files:
            data.update({f.path.as_rtp():db_new_path})
        logging.debug(f"FWTSet: rewrite batch: {json.dumps(data,indent=4)}")
        return data

    @property
    def files(self):
        return self._files

    @property
    def preferred(self):
        return self._preferred

    @preferred.setter
    def preferred(self,p):
        if p == False and self.preferred:
            self._files.append(self.preferred)
            self._preferred = False
        else:
            if p in self._files:
                if self._preferred:
                    self._files.append(self._preferred)
                self._preferred = p
                self._files.remove(p)
            else:
                raise ValueError("FWTSet: Preferred file not in set. Got"
                f" preferred as {p.path}. Set contains: \n" + 
                "\n".join([f.path.as_posix() for f in self._files]))
                    
    def choose_preferred(self,match=None,i=None):
        if match and type(match) == str: 
            logging.debug(f"FWTSet: testing set {self.id} with match {match}")
            match = re.compile(match)
        if match and type(match) != re.Pattern:
            raise ValueError("choose_preferred requires a regex string or" 
                            "compiled pattern for the match parmater")

        if match:
            for f in self._files:
                if match.search(str(f)):
                    self.preferred = f
                    logging.debug(f"FWTSet: preferred file found {self.preferred}")
                    break
        elif i != None and i < len(self._files):
            self.preferred = self._files[i]

        if not self.preferred:
            logging.debug(f"FWTSet: no match in {self.id} for {match}")
            return False
        return True

    def add_file(self,path,preferred=False):
        file = FWTFile(path,trash_dir=self.trash_dir)
        if not file in self._files:
            self._files.append(file)
        if preferred:
            self.preferred = file
        return True

    def __len__(self):
        preferred_count = 1 if self.preferred else 0
        return len(self._files) + preferred_count

    def __str__(self):
        files = "\n".join([str(f) for f in self._files])
        return f"id:{self.id}\npreferred:{self.preferred}\nfiles:\n{files}"

class FWTFilter:
    chain_type = None
    plugin_type = None
    _matches = []

    def __init__(self,exclude=False):
        self.exclude = exclude

    def _filter(self,p):
        raise NotImplementedError

    def _process(self,p):
        raise NotImplementedError   
    
    def __call__(self,p):
        if self.chain_type == "filter":
            return self._filter(p)
        elif self.chain_type == "processor":
            return self._process(p)
        else:
            raise NotImplementedError

class FileNamesFilter(FWTFilter):
    """file match. See pathlib.match"""
    chain_type = 'filter'
    plugin_type = 'file'
    def add_match(self,m,match_case=True,type="include"):
            self._matches.append(m)
    def _filter(self,p):
        for m in self._matches:
            if self.exclude:
                if p.match(m): continue
            else:
                if p.match(m): return p
        return False

class FileExtensionsFilter(FWTFilter):
    """case insensetive file extension match."""
    chain_type = 'filter'
    plugin_type = 'file'
    def add_match(self,m):
        if m[0] != '.': m = '.'+m
        self._matches.append(m)
    def _filter(self,p):
        e = p.suffix.lower()
        for m in self._matches:
            m = m.lower()
            if self.exclude:
                if e == m: continue 
            else:
                if e == m: return p
        return False

class DirNamesFilter(FWTFilter):
    """project relative dir match. See pathlib.match"""
    chain_type = 'filter'
    plugin_type = 'dir'
    def __init__(self,exclude=True):
        self.exclude = exclude
    def add_match(self,m):
        self._matches.append(m)
    def _filter(self,p):
        for m in self._matches:
            if self.exclude:
                if p.match(m):
                    logging.debug(f"DirNamesFilter: exclude matched {p}")
                    return False
            else:
                if p.match(m): return p
        return p if self.exclude else False

class FWTChain:
    def __init__(self):
        self._dir_filter_chain = []
        self._file_filter_chain = []
        self._file_processor_chain = []

    def add_filter(self,filter):
        if filter.plugin_type == 'dir' and callable(filter):
            self._dir_filter_chain.append(filter)
        if filter.plugin_type == 'file' and callable(filter):
            self._file_filter_chain.append(filter)

    def _dir_filter(self,p,cb=None):
        for df in self._dir_filter_chain:
            p = df(p)
        if p and self._dir_cb(p):
            yield from self._dir_cb(p)
        elif p:
            yield p

    def _file_filter(self,p):
        for ff in self._file_filter_chain:
            p = ff(p)
        if p:
            yield from self._file_processor(p)

    def _file_processor(self,p):
        for fp in self._file_processor_chain:
            p = fp(p)
        if p:
            yield p
    
    def _dir_cb(self,*args,**kwargs):
        raise NotImplementedError

    def __iter__(self):
        raise NotImplementedError

class FWTScan(FWTChain):
    def __init__(self,root):
        super().__init__()
        self._root = root
        self._dir_cb = self._walk

    def _walk(self,p):
        for p in p.iterdir():
            if p.is_dir():
                yield from self._dir_filter(p)
            else:
                yield from self._file_filter(p)

    def __iter__(self):
        return self._walk(self._root) 

class FWTFileWriter(AbstractContextManager):
    def __init__(self,*args,**kwargs):
        self.__read_fd = False
        self._trash_overwrite = True
        self._trash_dir = False
        self.setup(*args,**kwargs)

    def setup(self,dest_path=None,trash_dir=None,read_fd=None,
              trash_overwrite=None):
        if read_fd != None:
            self.__read_fd = read_fd
        if trash_overwrite != None:
            self._trash_overwrite = trash_overwrite
        if trash_dir != None:
            self._trash_dir = _Path_(trash_dir)
            self._trash_dir.parent.mkdir(parents=True,exist_ok=True)
        if dest_path:
            self._dest_path = Path(dest_path)
            self._temp_path = self._dest_path.with_suffix('.part')

    def _open_read_fd(self):
        return self._dest_path.open("r+t",encoding="utf-8")

    def _open_write_fd(self):
        return self._temp_path.open("w+t",encoding="utf-8")

    def __exit__(self,*args):
        if self.__read_fd:
            self.read_fd.close()
        self.write_fd.flush()
        if self.write_fd.tell() == 0:
            self.write_fd.close()
            self._temp_path.unlink()
            return
        self.write_fd.close()
        if self._trash_dir:
            rel_path = self._dest_path.relative_to(self._dest_path.parents[1])
            trash_path = self._trash_dir / rel_path
            trash_path.parent.mkdir(parents=True,exist_ok=True)
            do_overwrite = trash_path.exists() and self._trash_overwrite
            if do_overwrite or not trash_path.exists():
                try:
                    self._dest_path.replace(trash_path)
                except Exception as err:
                    self._temp_path.unlink()
                    raise err
        self._temp_path.rename(self._dest_path)

    def __enter__(self):
        if not self._dest_path:
            raise ValueError("dest_path not provided")
        self.write_fd = self._open_write_fd()
        self.write = self.write_fd.write
        if self.__read_fd:
            self.read_fd = self._open_read_fd()
            self.read = self.read_fd.read
        return self

    def __call__(self,*args,**kwargs):
        self.setup(*args,**kwargs)
        return self


class FWTProjectDb:
    def __init__(self,project_dir,driver,trash_dir='trash'):
        self.project_dir = FWTPath(project_dir,require_project=True)
        self.data = None
        self.packs = None
        if trash_dir:
            if not Path(trash_dir).is_absolute():
                trash_dir = self.project_dir / trash_dir
            trash_dir = find_next_avaliable_path(
                trash_dir / "session.0")
            self.trash_dir = trash_dir
        for dbtype in 'data','packs':
            dbs = {f.stem:driver(f,trash_dir=trash_dir) for f in self.project_dir.glob(f'{dbtype}/*db')}
            db_sns = SimpleNamespace(**dbs)
            setattr(self,dbtype,db_sns) 
    def __iter__(self):
        return chain(self.data.__dict__.values(),
                     self.packs.__dict__.values())

class FWTDb:
    def __init__(self,data_file,trash_dir=None):
        self.file_context = FWTFileWriter(trash_dir=trash_dir,trash_overwrite=False)
        self._data_file = Path(data_file)

    def writer(self):
        return self.file_context(dest_path=self.path)

    @property
    def path(self):
        return self._data_file.as_posix()

class FWTTextDb(FWTDb):
    """A lightweight object to manage reading / writing text files"""
    def __init__(self,data_file,*args,**kwargs):
        super().__init__(data_file,*args,**kwargs)

    def open(self):
        return FWTFileWriter(dest_path=self.path)

    def __iter__(self):
        return (line for i,line in enumerate(open(self.path,'r+t')))

class FWTNeDB(FWTDb):
    """A lightweight object to manage reading and writing NeDB files"""
    def __init__(self,data_file,*args,**kwargs):
        super().__init__(data_file,*args,**kwargs)
        self._data = []
        self._ids = {}

    @property
    def ids(self):
        return tuple(self._ids.keys())

    def genId(self):
        n = "".join(random.choices(string.ascii_letters + string.digits,k=16))
        return n

    def find(self,query,projection=None):
        raise NotImplementedError

    def update(self,query,update,options):
        raise NotImplementedError

    def find_generator(self, lookup_val, lookup_key="_id", lookup_obj=None):
        if lookup_obj == None: lookup_obj = self._data
        if isinstance(lookup_obj, dict):
            logging.debug("obj_lookup_generater: found dict object")
            for k, v in lookup_obj.items():
                if k == lookup_key and (v == lookup_val or lookup_val == "*"):
                    yield lookup_obj
                else:
                    yield from self.find_generator(v, lookup_val, lookup_key)
        elif isinstance(lookup_obj, list):
            logging.debug("obj_lookup_generator: found list object")
            for item in lookup_obj:
                yield from self.find_generator(item, lookup_val, lookup_key)
        else:
            logging.debug("obj_lookup_generator: got unknown object")

    def load(self):
        with open(self.path,'r') as f:
            self._data = [json.loads(x) for x in f.readlines()]
        for i,obj in enumerate(self._data,start=0):
            self._ids.update({obj["_id"]:i})

    def save(self):
        with self.writer() as f:
            writer = jsonlines.Writer(f.write_fd,compact=True,sort_keys=True)
            writer.write_all(self._data)

    def __getitem__(self,key):
        if key in self._ids.keys():
            return self._data[self._ids[key]]
        raise KeyError

    def __iter__(self):
        if not self._data:
            self.load()
        return self._data.__iter__()

class FWTAssetDownloader:
    def __init__(self,project_dir):
        self.r20re = re.compile(r'(?P<url>(?P<base>https://s3\.amazonaws\.com/files\.d20\.io/images/(?:[^/]+/)+)(?:\w+)\.(?P<ext>png|jpg|jpeg)[^"]*)')
        self.urlRe = re.compile(r'\w+://[^"]*\.(?P<ext>(png)|(jpg)|(webp))')
        self.project_dir = FWTPath(project_dir)
        self.agent_string = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.87 Safari/537.36'

    def checkUrl(self,url):
        req = urllib.request.Request(
            url, method='HEAD', headers={'User-Agent':self.agent_string})
        resp = urllib.request.urlopen(req)
        if resp.status == 200:
            return True
        else:
            logging.error(f"URL {url} returned HTTP Status of {resp.status}")
            return False

    def downloadUrl(self,u,path):
        url = urllib.parse.urlsplit(u)
        url_path = urllib.parse.unquote(url.path)
        url = url._replace(path=urllib.parse.quote(url_path))
        url = urllib.parse.urlunsplit(url)
        r20_match = self.r20re.search(url)
        if r20_match:
            url_parts = r20_match.groupdict()
            for size in ('original','max','med'):
                check_url = f'{url_parts["base"]}{size}.{url_parts["ext"]}'
                if self.checkUrl(check_url):
                    url = check_url
                    break

        logging.debug(f"downloading URL {url}")
        req = urllib.request.Request(
            url,method='GET',headers={'User-Agent':self.agent_string})
        resp = urllib.request.urlopen(req)
        if resp.status == 200:
            with open(path, "wb") as f:
                f.write(resp.read())

    def formatFilename(self,name):
        filename = re.sub(r'[^A-Za-z0-9\-\ \.]','',name)
        filename = filename.replace(" ","-").lower()
        filename = re.sub(r'^\.','',filename)
        return(filename)

    def download_item_images(self,item,asset_dir='items'):
        item_name = item["name"]
        item_img = item["img"]
        item_desc = item["data"]["description"]["value"]
        if not item_img:
            logging.error(f"\nNo image set for {item_name}. Skipping \n")
            return False
        logging.debug(f"checking if item img, {item_img}, is a URL")
        img_match = self.urlRe.match(item_img)
        desc_match = self.urlRe.search(item_desc)
        if not img_match:
            try:
                item_dir = Path(item_img).parent.relative_to(self.project_dir.to_rpd())
            except ValueError:
                pass
        else:
            logging.debug(f"Item image is a URL {item_img}")
            item_dir = Path(asset_dir) / self.formatFilename(item_name)
            filename = self.formatFilename(f"image.{img_match.group('ext')}")
            target_path = FWTPath(self.project_dir / item_dir / filename,exists=False)
            target_path.parent.mkdir(parents=True,exist_ok=True)
            self.downloadUrl(item_img,target_path)
            if target_path.exists():
                item['img'] = target_path.as_rtp()
                item_img = item['img']
            else:
                raise FileNotFoundError(f"Downloaded file {target_path} was not found")
        if desc_match:
            urls = set()
            if not item_dir:
                item_dir = Path(asset_dir) / self.formatFilename(item_name)
            for match in self.urlRe.finditer(item_desc):
                if match[0] in urls:
                    continue
                urls.add(match[0])
                filename = self.formatFilename(f"{item_name}-desc-{len(urls)}.{match.group('ext')}")
                target_path = FWTPath(self.project_dir / item_dir / filename,exists=False)
                target_path.parent.mkdir(parents=True,exist_ok=True)
                self.downloadUrl(match[0],target_path)
                if target_path.exists():
                    logging.debug(f"downloaded {match[0]} to {target_path}")
                    item_desc = item_desc.replace(
                        match[0],target_path.as_rtp())
                else:
                    raise FileNotFoundError(f"Downloaded file {target_path} was not found")   
            item["data"]["description"]["value"] = item_desc

    def download_actor_images(self,actor,asset_dir='characters'):
        actor_img = actor["img"]
        token_img = actor["token"]["img"]
        actor_type = actor["type"]
        actor_bio = actor['data']['details']['biography']['value']
        actor_name = actor["name"]
        character_dir = ""
        if not actor_img or not token_img:
            logging.error(f"\nNo image file for {actor_name}. Skipping\n")
            return False
        logging.debug(f"checking {actor_img}")
        img_match = self.urlRe.match(actor_img) if actor_img else False
        logging.debug(f"checking {token_img}")
        token_match = self.urlRe.match(token_img) if token_img else False
        bio_match = self.r20re.search(actor_bio) if actor_bio else False
        if not img_match:
            try:
                character_dir = Path(actor_img).parent.relative_to(self.project_dir.to_rpd())
            except ValueError:
                pass
        if not token_match and not character_dir:
            try:
                character_dir = Path(token_img).parent.relative_to(self.project_dir.to_rpd())
            except ValueError:
                pass
        if img_match:
            logging.debug(f"Found actor imgage URL match: {actor_name} - {actor_img}")
            if not character_dir:
                character_dir = Path(asset_dir) / self.formatFilename(actor_name)
            filename = self.formatFilename(f"avatar.{img_match.group('ext')}")
            target_path = FWTPath(self.project_dir / character_dir / filename,exists=False)
            target_path.parent.mkdir(parents=True,exist_ok=True)
            self.downloadUrl(actor_img,target_path)
            if target_path.exists():
                actor['img'] = target_path.as_rtp()
                actor_img = actor['img']
            else:
                raise FileNotFoundError(f"Downloaded file {target_path} was not found")
        
        if token_match:
            filename = self.formatFilename(f"token.{token_match.group('ext')}")
            target_path = FWTPath(self.project_dir / character_dir / filename,exists=False)
            target_path.parent.mkdir(parents=True,exist_ok=True)
            self.downloadUrl(token_img,target_path)
            if target_path.exists():
                actor["token"]["img"] = target_path.as_rtp()
            else:
                raise FileNotFoundError(f"Downloaded file {target_path} was not found")

        if bio_match:
            urls = set()
            if not character_dir:
                character_dir = Path(asset_dir) / self.formatFilename(actor_name)
            for match in self.r20re.finditer(actor_bio):
                if match.group('url') in urls:
                    continue
                urls.add(match.group('url'))
                filename = f"{actor_name}-bio-{len(urls)}.{match.group('ext')}"
                target_path = FWTPath(self.project_dir / character_dir / filename,exists=False)
                target_path.parent.mkdir(parents=True,exist_ok=True)
                self.downloadUrl(match.group('url'),target_path)
                if target_path.exists():
                    logging.debug(f"downloaded {match.group('url')} to {target_path}")
                    actor_bio = actor_bio.replace(
                        match.group('url'),target_path.as_rtp())
                else:
                    raise FileNotFoundError(f"Downloaded file {target_path} was not found")   
            actor['data']['details']['biography']['value'] = actor_bio
