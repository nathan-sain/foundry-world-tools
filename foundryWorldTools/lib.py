import json, filecmp, time, pprint, glob, re, logging, itertools, sys, shutil
import jmespath
from os import path,listdir,walk,rename,renames,stat,chown,makedirs
from shutil import copy
from collections import UserDict
from tempfile import gettempdir


fvtt_sys_re = re.compile(r'.*Data/')

class genericobject:
    def __getitem__(self,i):
        for v in self.__dict__.values():
            if isinstance(v,NotNeDB):
                for r in v[i]: yield r
        

class FWT_Config(UserDict):
    """An object for loading and saving JSON config files"""
    def load(self,file_name):
        with open(file_name,"r") as cf:
            config_data = json.load(cf)
            self.data.update(config_data)
            self.config_file = file_name
    def save(self):
        with open(self.config_file,"w") as cf:
            json.dump(self.data,cf)
    def create_config(self,file_name):
        try:
            if not path.exists(file_name):
                    temp_config_file = path.join(gettempdir(),"fwt.json")
                    self.config_file = temp_config_file
                    self.save()
                    renames(temp_config_file,file_name)
                    self.config_file = file_name
        except:
            logging.warning(f"unable to create config file {sys.exc_info()[0]}")

        



class NotNeDB:
    """A lightweight object to manage reading NeDB files"""
    def __init__(self,data_file):
        self.data_file = data_file
        self.data = []
        logging.debug(f"begin loading NotNeDB file {self.data_file}")
        self.load()
        logging.debug(f"finished loading NotNeDB file {self.data_file}")
    def load(self):
        with open(self.data_file,'r') as f:
            self.data = [json.loads(x) for x in f.readlines()]
    def data(self):
        return self.data
    def dumps(self):
        return self.data
    def dump(self):
        file_json = [json.dumps(l) for l in self.data]
        print(file_json)
    def search(self,q):
        return jmespath.search(q,self.data)
    def __getitem__(self,i):
        return obj_lookup_generator(self.data,i)

class FWT_FileManager:
    """An object for dealing with files and updating foundry db when file paths change"""
    def __init__(self,base_dir,file_extensions=[]):
        if not path.exists(path.join(base_dir,"world.json")):
            raise ValueError(f"Directory {base_dir} does not appear to be a FVTT world directory")
        self.world_dir = path.abspath(base_dir)
        self.dir_exclusions = []
        self.fvtt_data_dir = findFvttRoot(self.world_dir)+"/Data"
        pprint.pprint(self.fvtt_data_dir)
        self.trash_dir = path.join(self.world_dir,"Trash")
        self.add_dir_exclusion(self.trash_dir)
        self.add_dir_exclusion(path.join(self.world_dir,"data"))
        self.add_dir_exclusion(path.join(self.world_dir,"packs"))
        self.file_extensions = file_extensions
        self.files = []
        self.rewrite_names_pattern = None
    def add_dir_exclusion(self,dir):
        if not dir in self.dir_exclusions:
            self.dir_exclusions.append(dir)
    def add_file_extension(self,ext):
        if not ext in self.file_extensions:
            self.file_extensions.append(ext)
    def scan(self):
        self.file_data = get_files(
                    self.world_dir,
                    extensions=self.file_extensions,
                    excludes=self.dir_exclusions
                    )
        for p in self.file_data['files']:
                f = FWT_File(p)
                self.files.append(f)
    def renameall(self):
        if self.rewrite_names_pattern:
            for f in self.files:
                p = f.get_path()
                if f.set_new_path(re.sub(self.rewrite_names_pattern,'',p)):
                    logging.debug(f"process_file_queue: updated file path with pattern {self.rewrite_names_pattern}")
    def generate_rewrite_queue(self):
        rewrite_queue = {}
        for f in self.files:
            np = f.get_new_path()
            if np:
                rewrite_queue.update({f.get_path():np})
        rewrite_rel_paths = {k.replace(self.fvtt_data_dir+'/',''):v.replace(self.fvtt_data_dir+'/','')
                             for (k,v) in rewrite_queue.items()}
        pprint.pprint(rewrite_rel_paths)
        self.rewrite_queue = rewrite_rel_paths
    def get_rewrite_queue(self):
            return self.rewrite_queue
    def process_rewrite_queue(self):
        if(len(self.rewrite_queue)):
            replace_string_in_db(path.join(self.world_dir,"data"),batch=self.rewrite_queue)
            replace_string_in_db(path.join(self.world_dir,"packs"),batch=self.rewrite_queue)
    def process_file_queue(self):
        """do file renames and deletions"""   
        for f in self.files:
            if f.get_new_path() and f.keep_src:
                f.copy()
            if f.get_new_path():
                f.rename()
            if f.get_trash_path():
                f.trash()
    def pprint(self):
        pprint.pprint(self.files)
    def get_world_dir(self):
        return self.world_dir
    def add_rewrite_names_pattern(self,pattern):
        self.rewrite_names_pattern = pattern
    def load_preset(self,preset_obj):
        allowed = {"file_extensions","dir_exclusions","rewrite_names_pattern"}
        found_keys = allowed.intersection(set(preset_obj.keys()))
        presets = {k:v for (k,v) in preset_obj.items() if k in found_keys}
        self.__dict__.update(presets)
        return True
    def add_file(self,fpath):
        file = FWT_File(fpath)
        self.files.append(file)
        return file

class FWT_File:
    """An object representing a single Foundry asset file"""
    def __init__(self,path):
        self.path = path
        self.new_path = ""
        self.locked = False
        self.trash_path = ""
        self.keep_src = False
    def rename(self):
        if self.new_path and not self.keep_src:
            if not path.exists(self.new_path):
                logging.debug(f"Renaming {self.path} -> {self.new_path}")
                renames(self.path,self.new_path)
            else:
                raise ValueError(f"Can't rename file {self.path}\nTarget {self.new_path} exists!")
            self.old_path = self.path
            self.path = self.new_path
            self.new_path = ""
            logging.debug(f"rename:completed rename of {self.old_path} -> {self.path}")
            return True
        return False 
    def copy(self):
        if self.new_path:
            if not path.exists(self.new_path):
                makedirs(path.dirname(self.new_path), exist_ok=True)
                logging.debug(f"Copying {self.path} -> {self.new_path}")
                shutil.copy2(self.path,self.new_path)
            else:
               raise ValueError(f"Can't copy file {self.path}\nTarget {self.new_path} exists!")
               self.copy_of = self.path
               self.path = self.new_path
               self.new_path = ""
               logging.debug(f"copy:completed copy of {self.copy_of} -> {self.path}")
            return True
    def set_trash_path(self,trash_path):
        if trash_path:
            self.trash_path = trash_path
        return True
    def set_keep_src(self):
        self.keep_src=True
    def trash(self):
        self.new_path = self.trash_path
        return self.rename()
    def set_new_path(self,new_path):
        if not new_path == self.path:
            self.new_path = new_path
            return True
        else: return False
    def get_new_path(self):
        return self.new_path
    def get_path(self):
        return self.path
    def get_trash_path(self):
        return self.trash_path
    def unset_new_path(self):
        self.new_path = None
        return True
    def __str__(self):
        if self.new_path:
           return f"{self.path} -> {self.new_path}"
        else: return f"{self.path}"

class FWT_SetManager(FWT_FileManager):
    """An object for dealing with duplicate assets"""
    def __init__(self,base_dir,preferred_patterns=[],file_extensions=[]):
        super().__init__(base_dir)
        self.preferred_patterns = preferred_patterns
        self.rewrite_queue = {}
        for pp in preferred_patterns: self.add_preferred_pattern(pp)
        self.stats = {"total files":0,"unique files":0}
        self.fwtsets = []
        self.detect_dup_byname = False
        self.detect_dup_bycontent = False
    def add_preferred_pattern(self,pp):
        self.preferred_patterns.append(pp)
    def set_detect_method(self,bycontent=False,byname=False):
        if (bycontent == True and byname == True) or (bycontent == False and byname == False):
            raise ValueError(f"cannot set bycontent={bycontent} and by byname={byname}")
        elif type(bycontent) == bool and type(byname) == bool:
            self.detect_dup_bycontent=bycontent
            self.detect_dup_byname=byname
            return True
        else:
            raise ValueError("Logic error")    
    def load_preset(self,preset_obj):
        allowed = {"detect_dup_bycontent","preferred_patterns","detect_dup_byname","file_extensions","dir_exclusions","rewrite_names_pattern"}
        found_keys = allowed.intersection(set(preset_obj.keys()))
        presets = {k:v for (k,v) in preset_obj.items() if k in found_keys}
        self.__dict__.update(presets)
        return True
    def scan(self):
        self.dup_data = get_files(
                    self.world_dir,
                    byname=self.detect_dup_byname,
                    bycontent=self.detect_dup_bycontent,
                    extensions=self.file_extensions,
                    excludes=self.dir_exclusions
                    )
        logging.debug(f"scan: scanned {self.dup_data['numfiles']} files.")
        logging.debug(f"scan: file types scanned: {','.join(self.dup_data['types'])}")
        if len(self.dup_data['dups']):
            self.fwtsets.extend([FWT_Set(self,files=v) for k,v in self.dup_data['dups'].items() if len(v) > 1])
            logging.debug(f"scan: found {len(self.fwtsets)} sets")
    def pprint(self):
        for dup in self.fwtsets: print(dup)
    def process_file_queue(self):
        """do file renames"""   
        for f in self.fwtsets:
            f.get_preferred().rename()
        for f in self.fwtsets:
            for d in f.get_dups():
                try:
                    d.trash()
                except ValueError as ve:
                    print(f"Error with set:\n {pprint.pprint(d)}\n\n{ve}")
    def set_preferred_on_all(self):
        for dup in self.fwtsets:
            for pref in self.preferred_patterns:
                pref = pref.replace('<world_dir>',self.world_dir)
                if dup.set_preferred(search=pref):
                    logging.debug(f"set_preferred_on_all: set prefered file using pattern {pref}")
                    break
            if not dup.get_preferred():
                logging.debug(f"set_preferred_on_all: set prefered file to set item 0")
                dup.set_preferred(i=0)
            if self.rewrite_names_pattern:
                if dup.rewrite_preferred_path(self.rewrite_names_pattern):
                    logging.debug(f"process_file_queue: updated file path with pattern {self.rewrite_names_pattern}")
    def generate_rewrite_queue(self):
        fwt_dup_queue = {}
        for dup in self.fwtsets:
            fwt_dup_queue.update(dup.get_rewrite_data())
        fixed_fwt_paths = {get_fvtt_sys_path(k):get_fvtt_sys_path(v) for (k,v) in fwt_dup_queue.items()}
        pprint.pprint(fixed_fwt_paths)
        self.rewrite_queue = fixed_fwt_paths
    def add_set(self,files):
        fwtset = FWT_Set(self,files=files)
        self.fwtsets.append(fwtset) 


   
class FWT_Set:
    """An object that contains a set of files representing the same asset 
    and methods for choosing a preferred file and removing the rest
    """
    def __init__(self,parent,hash=None,files=[]):
        self.hash = hash
        self.files = [FWT_File(f) for f in files]
        self.preferred = None
        self.parent = parent
    def rewrite_preferred_path(self,expression):
        p = self.preferred
        pp = p.get_path()
        npp = path.sep.join([re.sub(expression,'',e) for e in pp.split(path.sep)])
        if p.set_new_path(npp):
            logging.debug(f"fixed preferred dup path {p.get_path()} -> {p.get_new_path()}")
            return p.get_new_path()
        return False
    def get_rewrite_data(self):
        rewrite_data = {}
        p,np = self.preferred.get_path(),self.preferred.get_new_path()
        if np: 
            target = np
            rewrite_data[p] = np
        else:
            target = p
        rewrite_data.update({f.get_path():target for f in self.files})
        return rewrite_data
    def set_preferred(self,i=None,search=""):
        if self.preferred:
            return False
        if search and type(search) == str: search = re.compile(search)
        p = None
        if search:
            for f in self.files:
                if search.search(str(f)): 
                    p = f
                    break
        elif i != None and i < len(self.files):
            p = self.files[i]
        if not p:
            return False
        self.files.remove(p)
        self.preferred = p
        for file in self.files: 
            file.set_trash_path(file.get_path().replace(self.parent.get_world_dir(),self.parent.trash_dir))
        return True
    def reset_preferred(self):
        if self.preferred:
            self.files.append(self.preferred)
            self.preferred = None
            for f in self.files: f.unset_new_path()
        return True
    def add_preferred(self,fpath):
        if not self.preferred:
            file = FWT_File(fpath)
            self.files.append(file)
            return self.set_preferred(i=self.files.index(file))
        return False
    def add_file(self,fpath):
        file = FWT_File(fpath)
        self.files.append(file)
        if self.preferred:
            file.set_trash_path(file.get_path().replace(self.parent.get_world_dir(),self.parent.trash_dir))
        return True
    def get_preferred(self):
        return self.preferred
    def get_dups(self):
        return self.files
    def __str__(self):
        files = "\n".join([str(f) for f in self.files])
        return f"hash:{self.hash}\npreferred:{self.preferred}\nfiles:\n{files}"       

def replace_string_in_db(path,find=None,replace=None,batch={},whole_value=True):
    if find and replace: batch[find] = replace
    lines_changed = 0
    logging.debug(f"replace_string_in_db: there are {len(batch)} items in the batch")
    dbfiles = get_db_file_paths(path)
    for df_path in dbfiles:
        tf_path = unique_filename(df_path+".tmp")
        logging.debug(f"replace_string_in_db: reading from file {df_path}")
        logging.debug(f"replace_string_in_db: writing to file {tf_path}")
        with open(df_path,'r') as df, open(tf_path,"w") as tf:
            for idx, line in enumerate(df):
                for f,r in batch.items():
                    if whole_value:
                        line = line.replace(f'"{f}"',f'"{r}"')
                    else:
                        line = line.replace(f,rcd )
                tf.write(line)
        bf_path = unique_filename(df_path+".bak")
        logging.debug(f"replace_string:in_db: renaming {df_path} to {bf_path}")
        rename(df_path,bf_path)
        logging.debug(f"replace_string:in_db: renaming {tf_path} to {df_path}")
        rename(tf_path,df_path)
        cpSecPerm(bf_path,df_path)
    return {"files":dbfiles,"lines_changed":lines_changed}
            
def unique_filename(output_filename):
    n = ''
    while path.exists(f'{output_filename}{str(n)[1:]}'):
        if isinstance(n, str): n = -0.1
        n += 0.1
    return f'{output_filename}{str(n)[1:]}'   

def obj_lookup_generator(lookup_obj, lookup_val, lookup_key="_id"):
    if isinstance(lookup_obj, dict):
        logging.debug("obj_lookup_generater: found dict object")
        for k, v in lookup_obj.items():
            if k == lookup_key and (v == lookup_val or lookup_val == "*"):
                logging.debug(f"found object with {lookup_key} == {lookup_val}")
                yield lookup_obj
            else:
                yield from obj_lookup_generator(v, lookup_val, lookup_key)
    elif isinstance(lookup_obj, list):
        logging.debug("obj_lookup_generator: found list object")
        for item in lookup_obj:
            yield from obj_lookup_generator(item, lookup_val, lookup_key)
    else:
        logging.debug("obj_lookup_generator: got unknown object")

def get_db_file_paths(search_path):
    """return a list of db file paths. path can a single file, directory, pattern,or world root"""
    if path.exists(path.join(search_path,"world.json")):
        dbdir = path.join(search_path,"data")
        dbfiles = glob.glob(path.join(dbdir,"*.db"))
    elif path.isdir(search_path):
        dbfiles = glob.glob(path.join(search_path,"*.db"))
    elif "db" in search_path:
        dbfiles = glob.glob(search_path)
    else:
        raise ValueError(f"{search_path} is not a valid. No db files found")
    dbfiles = [path.abspath(f) for f in dbfiles if f[-2:]=="db" and path.isfile(f)]
    logging.debug(f"get_db_file_paths({search_path}) found files {','.join(dbfiles)}")
    return dbfiles

def load_dbdir(search_path):
    db = genericobject()
    db.index = {}
    dbfiles = get_db_file_paths(search_path)
    for dbfile in dbfiles:
        if path.exists(dbfile):
            dbname = path.basename(path.splitext(dbfile)[0])
            setattr(db,dbname,NotNeDB(dbfile))
            logging.debug(f"loaded json fromn dbfile {dbfile}")
            db.index[dbname] = dbfile
        else:
            raise ValueError(f"Database file {dbfile} doesn't exist!")
    return db

def detect_dup_contents(dups,fpath):
    with open(fpath,'rb') as f:
        fhash = hash(f.read(4096))
        if fhash == 0: return # empty file
    while True:
        if fhash not in dups:
            dups[fhash] = [fpath]
            break
        if filecmp.cmp(fpath,dups[fhash][0],shallow=False):
            dups[fhash].append(fpath)
            break
        fhash += 1

def detect_dup_name(dups,fpath):
    fn,fe = path.splitext(fpath)
    dups[fn] = dups.get(fn,[])+[fpath]


def get_files(worldpath,extensions=None,excludes=None,bycontent=False,byname=False):
    """https://codereview.stackexchange.com/questions/212430/identify-duplicate-files"""
    numfiles = numskipped = 0
    t0 = time.time()
    files = []
    dups = {}
    types = {}
    for root,dnames,fnames in walk(worldpath):
        for e in excludes:
            if e in root:
                fnames = []
        for fname in fnames:
            fext = path.splitext(fname)[1]
            if extensions and not fext in extensions:
                continue
            types[fext] = types.get(fext,0)+1
            fpath = path.join(root,fname)
            try:
                if bycontent: detect_dup_contents(dups,fpath)
                elif byname: detect_dup_name(dups,fpath)
                files.append(fpath)
            except OSError:
                numskipped += 1
                continue
            numfiles += 1
    return {'types':types,'files':files, 'dups':dups, 'numfiles':numfiles, 'numskipped':numskipped, 'time':time.time()-t0} 

def get_fvtt_sys_path(file_path):
    fspm = fvtt_sys_re.sub('',file_path)
    if fspm: return fspm
    raise ValueError("unable to determine fvtt system path")

def find_list_dups(c):
        '''sort/tee/izip'''
        a, b = itertools.tee(sorted(c))
        next(b, None)
        r = None
        for k, g in zip(a, b):
            if k != g: continue
            if k != r:
                yield k
                r = k

def findWorldRoot(dir):
    if dir == '/': return False
    try:
        pisd = path.isfile(dir)
        file_list = listdir(dir)
    except:
        return findWorldRoot(path.dirname(dir))
    if pisd or not 'world.json' in file_list: 
        return findWorldRoot(path.dirname(dir))
    return dir

def findFvttRoot(dir):
    if dir == '/': return False
    try:
        pisd = path.isfile(dir)
        file_set = set(listdir(dir))
    except:
        return findWorldRoot(path.dirname(dir))    
    if pisd or not {'Data','Config'}.issubset(file_set): 
        return findFvttRoot(path.dirname(dir))
    return dir


def cpSecPerm(src,target):
    st = stat(src)
    chown(target, st.st_uid, st.st_gid)
    shutil.copymode(src, target)

