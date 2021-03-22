# vim: expandtab smarttab shiftwidth=4 softtabstop=4
# -*- coding: utf-8 -*-
import os
import sys
import getopt
import json
import re
import functools
from ordereddict import OrderedDict # from collections import OrderedDict
import socket
import time
import errno
import json
import logging
import logging.handlers
import textwrap
import xml.etree.ElementTree
import xml.sax.saxutils
import commands
from datetime import datetime, timedelta
from subprocess import (Popen, PIPE)
from operator import eq as isequal
# import rados
from rados import (Rados,
                   LIBRADOS_OP_FLAG_FADVISE_DONTNEED,
                   LIBRADOS_OP_FLAG_FADVISE_NOCACHE,
                   LIBRADOS_OP_FLAG_FADVISE_RANDOM)

# import rbd
from rbd import (RBD, Group, Image, ImageNotFound, InvalidArgument, ImageExists,
                 ImageBusy, ImageHasSnapshots, ReadOnlyImage,
                 FunctionNotSupported, ArgumentOutOfRange,
                 DiskQuotaExceeded, ConnectionShutdown, PermissionError,
                 RBD_FEATURE_LAYERING, RBD_FEATURE_STRIPINGV2,
                 RBD_FEATURE_EXCLUSIVE_LOCK, RBD_FEATURE_JOURNALING,
                 RBD_MIRROR_MODE_DISABLED, RBD_MIRROR_MODE_IMAGE,
                 RBD_MIRROR_MODE_POOL, RBD_MIRROR_IMAGE_ENABLED,
                 RBD_MIRROR_IMAGE_DISABLED, MIRROR_IMAGE_STATUS_STATE_UNKNOWN,
                 RBD_FEATURE_FAST_DIFF, RBD_FEATURE_OBJECT_MAP,
                 RBD_LOCK_MODE_EXCLUSIVE, RBD_OPERATION_FEATURE_GROUP,
                 RBD_SNAP_NAMESPACE_TYPE_TRASH)
import pdb
import timeit

# ###############################################################

class TestException(Exception):
    """ user's Exception: `TestException` class, derived from `Exception` """
    def __init__(self, message, errno=None):
        super(TestException, self).__init__(message)
        self.errno = errno

    def __str__(self):
        msg = super(TestException, self).__str__()
        if self.errno is None:
            return msg
        return '[errno {0}] {1}'.format(self.errno, msg)

    def __reduce__(self):
        return (self.__class__, (self.message, self.errno))

# ###############################################################
conf_file = "/etc/ceph/ceph.conf"
cluster = None
ioctx = None
pool_name = "pool-test"
pool_idx = 0
group_name = None
group_idx = 0
image_name = "image-test"
image_idx = 0
snap_name = "snap-test"
snap_idx = 0
#IMG_SIZE = 8 << 30 # 8 GiB
IMG_SIZE = 10 << 30 # 8 GiB
#IMG_SIZE = 1 << 30 # 8 GiB
IMG_ORDER = 22 # 4 MiB objects
record_idx = 0
output_info = OrderedDict()
output_file = None
output_apilist = []
diff_file = None
do_diff_result = False

###

ioctx  = None
features = None


# ###############################################################
def record_rbdapi_test(apiname, retobj, *paras):
    global record_idx
    record_idx += 1
    para_list = OrderedDict()
    argv_idx = 1
    for para in paras:
        para_list['argv['+str(argv_idx)+']'] = typefilter(para)
        argv_idx += 1

    record = OrderedDict()
    record['name'] = str(apiname)
    record['id'] = record_idx
    record['argv'] = para_list
    record['return'] = typefilter(retobj)
    output_apilist.append(record)

def mytimeit(f):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        res = f(*args, **kwargs)
        end_time = time.time()
        print("%s函数运行时间为：%.2fs res:%s" %(f.__name__, end_time - start_time, res))
        record_rbdapi_test("%s func cost time is: %.2fs" % (f.__name__, end_time - start_time), res)
        return res
    return wrapper

def type2str(variate):
    if isinstance(variate,int):
        return str(variate)
    elif isinstance(variate,str):
        return str(variate)
    elif isinstance(variate,float):
        return str(variate)
    elif isinstance(variate,list):
        return str(list(variate))
    elif isinstance(variate,tuple):
        return str(tuple(variate))
    elif isinstance(variate,dict):
        return json.dumps(variate, indent=4)
    elif isinstance(variate,set):
        return str(set(variate))
    elif isinstance(variate,object):
        return str(id(variate))

def typefilter(variate):
    if variate is None:
        return variate
    elif isinstance(variate,int):
        return variate
    elif isinstance(variate,str):
        return variate
    elif isinstance(variate,float):
        return variate
    elif isinstance(variate,list):
        return variate
    elif isinstance(variate,tuple):
        return variate
    elif isinstance(variate,dict):
        return variate
    elif isinstance(variate,set):
        return variate
    else:
        return str(variate)

def rand_data(size):
    return os.urandom(size)

def decode_cstr(val, encoding="utf-8"):
    if val is None:
        return None

    return val.decode(encoding)

def run_sys_cmd(cmd):
    output = None
    p = Popen(cmd,shell=True,stdout=PIPE)
    p.wait()
    if p.returncode == 0:
        output = p.stdout.read()
    return output

# ##################################################
def load_output_file(filepath):
    with open(filepath, 'r') as f:
        output = json.loads(f.read())
        f.close()
        return output

def search_base_record(base, reocrd):
    if base is None or reocrd is None:
        return None

    for api in base:
        if api['name'] == reocrd['name'] and api['id'] == reocrd['id']:
            return api

    return {}

def reset_skip_keys(skip_keys):
    current = []
    left = []
    if len(skip_keys) == 0:
        return (current, left)

    for key in skip_keys:
        strlist = key.split('.')
        if len(strlist) == 1:
            current.append(str(strlist))
        else:
            current.append(str(strlist.pop(0)))
            left.append('.'.join(str for str in strlist))

    return current, left

def diff_dicts(dict1, dict2, skip_keys=[]):
    if isequal(dict1, dict2) is True:
        return True, None

    diff_keys = list(set(dict1.keys()) ^ set(dict2.keys()))
    for key in skip_keys:
        if key in diff_keys:
            diff_keys.remove(key)
    if len(diff_keys) > 0:
        return False, dict([(key,dict2[key]) for key in diff_keys if dict1[key] != dict2[key]])

    same_keys = list(set(dict1.keys()) & set(dict2.keys()))
    for key in skip_keys:
         if key in same_keys:
            same_keys.remove(key)

    if len(same_keys) > 0:
        return False, dict([(key,dict2[key]) for key in same_keys if dict1[key] != dict2[key]])

    return True, None


def diff_objs(baseobj, newobj, skip_keys=[]):
    if baseobj == None and newobj == None:
        return True, None
    
    if isinstance(baseobj,dict) and isinstance(newobj,dict):
        current, left = reset_skip_keys(skip_keys)
        ret, diff = diff_dicts(baseobj, newobj, current)
        if ret is False:
            for key in diff.keys():
                ret, diff = diff_objs(baseobj[key], newobj[key], left)
                if ret is False:
                    return False, diff
    
    if isequal(baseobj, newobj) is False:
        return False, newobj

    return True, None


def diff_api_return(apiname, base, new, skip_keys=[]):
    retval, diff = diff_objs(base, new, skip_keys)
    if retval is False:
        print('=========================================================================')
        print('diff api-return of "' + str(apiname) + '"')
        print('base :' + json.dumps(base, indent=4))
        print('new :' + json.dumps(new, indent=4))
        print('result: ' + str(retval))
        print('diff: ' + str(diff))

def diff_api_list(base, new, skip_keys=[]):
    for record_new in new:
        record_base = search_base_record(base, record_new)
        if record_base:
            diff_api_return(record_new['name'], record_base['return'], record_new['return'], skip_keys)

def diff_result():
    global do_diff_result
    if do_diff_result is True:
        global diff_file
        global output_file 
        base_output = load_output_file(diff_file)
        new_output = load_output_file(output_file)
        skip_keys = ['num_objects', 'kb_avail', 'kb_used', 'block_name_prefix']
        diff_api_list(base_output['api-list'], new_output['api-list'], skip_keys)

# ###############################################################

def Rados_obj_to_dict(cluster):
    cluster_info = OrderedDict()
    cluster_info['rados_id'] = cluster.rados_id
    cluster_info['conffile'] = cluster.conffile
    cluster_info['state'] = cluster.state
    # cluster_info['cluster'] = cluster.cluster
    cluster_info['conf_defaults'] = cluster.conf_defaults
    cluster_info['parsed_args'] = cluster.parsed_args
    cluster_info['monitor_callback'] = cluster.monitor_callback
    cluster_info['monitor_callback2'] = cluster.monitor_callback2    
    return cluster_info

def Ioctx_obj_to_dict(pool):
    pool_info = OrderedDict()
    pool_info['name'] = pool.name
    pool_info['state'] = pool.state
    pool_info['locator_key'] = pool.locator_key
    pool_info['nspace'] = pool.nspace
    # pool_info['lock'] = pool.lock
    pool_info['safe_completions'] = pool.safe_completions
    pool_info['complete_completions'] = pool.complete_completions
    return pool_info

def Image_obj_to_dict(image):
    imginfo = OrderedDict()
    # imginfo['id'] = image.id()
    imginfo['name'] = image.get_name()
    imginfo['size'] = image.size()
    imginfo['group'] = image.group()
    imginfo['flags'] = image.flags()
    imginfo['features'] = image.features()
    # imginfo['data_pool_id'] = image.data_pool_id()
    # imginfo['block_name_prefix'] = image.block_name_prefix()
    imginfo['snap_limit'] = image.get_snap_limit()
    imginfo['overlap'] = image.overlap()
    # imginfo['stat'] = image.stat()
    return imginfo

def SnapIterator_obj_to_dict(snapiterator):
    snaps_info = OrderedDict()
    snaps_list = []
    for snap in snapiterator:
        snaps_list.append(snap)

    snaps_info['snaps_list'] = snaps_list
    return snaps_list

# #####################
def get_file_dirpath(path):
    if os.path.isdir(path):
        return path
    elif os.path.isfile(path):
        return os.path.dirname(path)

def init_output_file():
    workdir = get_file_dirpath(sys.path[0])
    timestr = time.strftime("%Y%m%d%H%M%S", time.localtime())
    global output_file
    output_file = str(workdir) + "/output/result-apitest.json";
    output_dir = str(workdir) + "/output/"
    is_exists = os.path.exists(output_dir)
    if not is_exists:
        # 如果不存在则创建目录
        # 创建目录操作函数
        os.makedirs(output_dir)
    print(output_file)
    
def write_output_info_to_file(filename, info):
    with open(filename, 'w') as f:
        f.write(info)
        f.close()

def write_output_info():
    output_info['test-time'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    output_info['api-list'] = output_apilist
    jsoninfo = json.dumps(output_info, indent=4)
    write_output_info_to_file(output_file, jsoninfo)

def get_temp_pool_name():
    global pool_idx
    pool_idx += 1
    return pool_name + '-' + str(pool_idx)

def get_temp_image_name():
    global image_idx
    image_idx += 1
    return image_name + '-' + str(image_idx)

def get_temp_image_name_cur():
    global image_idx
    image_name_result = image_name + '-' + str(image_idx)
    image_idx -= 1
    return image_name_result

def get_temp_group_name():
    global group_idx
    group_idx += 1
    return group_name + '-' + str(group_idx)

def get_temp_snap_name():
    global snap_idx
    snap_idx += 1
    return snap_name + '-' + str(snap_idx)

def get_temp_snap_name_cur():
    global snap_idx
    snap_name_result = snap_name + '-' + str(snap_idx)
    snap_idx -= 1
    return snap_name_result

def ceph_mon_dump():
    result = run_sys_cmd('ceph mon dump --format=json')

def connect_cluster(conffile=conf_file):
    cluster = Rados(conffile=conffile)
    record_rbdapi_test('rados.Rados', Rados_obj_to_dict(cluster), conffile)
    print('new client for cluster')
    ret = cluster.connect()
    record_rbdapi_test('Rados.connect', ret)
    print('connect cluster')
    return cluster

def shutdown_cluster(cluster):
    ret = cluster.shutdown()
    record_rbdapi_test('Rados.shutdown', ret)
    print('shutdown cluster')

def get_cluster_stats(cluster):
    stats = cluster.get_cluster_stats()
    record_rbdapi_test('Rados.get_cluster_stats', stats)
    print('get cluster stats: ' + json.dumps(stats, indent=4))
    return stats

def get_cluster_fsid(cluster):
    fsid = cluster.get_fsid()
    record_rbdapi_test('Rados.get_fsid', fsid)
    print('get cluster fsid: ' + str(fsid))
    return fsid

def get_instance_id(cluster):
    insid = cluster.get_instance_id()
    record_rbdapi_test('Rados.get_fsid', insid)
    print('get cluster instance id: ' + str(insid))
    return insid

def list_pools(cluster):
    poollist = cluster.list_pools()
    record_rbdapi_test('Rados.list_pools', poollist)
    print('list pools: ' + str(poollist))
    return poollist

def create_pool(cluster, poolname=pool_name):
    ret = cluster.create_pool(poolname)
    record_rbdapi_test('Rados.create_pool', ret, poolname)
    print('create pool ' + poolname)
    return poolname

def open_pool(cluster, poolname=pool_name):
    ioctx = cluster.open_ioctx(poolname)
    record_rbdapi_test('Rados.open_ioctx', Ioctx_obj_to_dict(ioctx), poolname)
    print('open pool ' + poolname)
    return ioctx

def init_features():
    # RBD().pool_init(ioctx, True)
    features = os.getenv("RBD_FEATURES")
    features = int(features) if features is not None else 61
    return features

def close_pool(ioctx):
    ret = ioctx.close()
    record_rbdapi_test('ioctx.close', ret)
    print('close pool')

def delete_pool(cluster, poolname=pool_name):
    ret = cluster.delete_pool(poolname)
    record_rbdapi_test('ioctx.delete_pool', ret, poolname)
    print('delete pool ' + poolname)

@mytimeit
def create_image(ioctx, imagename, features):
    print("beging---create_image imagename:%s", imagename)
    if features is not None:
        print("beging ---RBD().create imagename:%s", imagename)
        ret = RBD().create(ioctx, imagename, IMG_SIZE, IMG_ORDER, 
                    old_format=False, features=int(features))
        print("end ---RBD().create imagename:%s", imagename)
        record_rbdapi_test('RBD.create', ret, Ioctx_obj_to_dict(ioctx), imagename, 
                    IMG_SIZE, IMG_ORDER, False, features)
        print("end ---record_rbdapi_test RBD().create imagename:%s", imagename)
    else:
        ret = RBD().create(ioctx, imagename, IMG_SIZE, IMG_ORDER, 
                    old_format=True)
        record_rbdapi_test('RBD.create', ret, Ioctx_obj_to_dict(ioctx), imagename, 
                    IMG_SIZE, IMG_ORDER, True)
    print('create image ' + imagename)
    print("end---create_image imagename:%s", imagename)
    return imagename

def open_image(ioctx, imagename):
    image = Image(ioctx, imagename)
    record_rbdapi_test('Image', Image_obj_to_dict(image), Ioctx_obj_to_dict(ioctx), imagename)
    #print('open image ' + imagename)
    return image

def close_image(image):
    ret = image.close()
    record_rbdapi_test('image.close', ret)
    #print('close image')

@mytimeit
def remove_image(ioctx, imagename):
    if imagename is not None:
        ret = RBD().remove(ioctx, imagename)
        record_rbdapi_test('RBD.remove', ret, Ioctx_obj_to_dict(ioctx), imagename)
        print('remove image ' + imagename)

def rename_image(ioctx, old, new):
    ret = RBD().rename(ioctx, old, new)
    record_rbdapi_test('RBD.rename', ret, Ioctx_obj_to_dict(ioctx), old, new)
    print('rename image: ' + old + ' -> ' + new)

def list_images(ioctx):
    imagelist = RBD().list(ioctx)
    record_rbdapi_test('RBD.list', imagelist, Ioctx_obj_to_dict(ioctx))
    print('list images: ' + ','.join(str(img) for img in imagelist))
    return imagelist

def get_image_size(image):
    imagesize = image.size()
    record_rbdapi_test('Image.size', imagesize)
    print('get image size = ' + str(imagesize))
    return imagesize

def reset_image_size(image, newsize):
    ret = image.resize(newsize)
    record_rbdapi_test('Image.resize', ret, newsize)
    print('set image size = ' + str(newsize))

def flatten_image(image):
    ret = image.flatten()
    record_rbdapi_test('Image.flatten', ret)
    print('flatten image')

def get_image_stat(image):
    stat = image.stat()
    record_rbdapi_test('Image.stat', stat)
    print('get image stat:' + json.dumps(stat, indent=4))

def get_image_features(image):
    features = image.features() 
    record_rbdapi_test('Image.features', features)
    print('get image features = ' + str(features))
    return features

def list_children(image):
    actual = image.list_children()
    # deduped = set([(poolname, image) for image in actual])
    record_rbdapi_test('Image.list_children', actual)
    print('list children')

def parent_info(image):
    (p_pool, p_image, p_snap) = image.parent_info()
    retdict = {}
    retdict['pool'] = p_pool
    retdict['image'] = p_image
    retdict['snap'] = p_snap
    record_rbdapi_test('Image.parent_info', retdict)
    print('get image parent info: ' + str(retdict))
    return (p_pool, p_image, p_snap)

def update_image_features(image, features, enabled):
    ret = image.update_features(features, enabled)
    record_rbdapi_test('Image.update_features', ret, features, enabled)
    print('update image features: ' + str(features) + ' <' + str(enabled) + '>')

def flush_image(image):
    ret = image.flush()
    record_rbdapi_test('Image.flush', ret)
    print('flush image')

def write_data_to_image(image, data, offset):
    ret = image.write(data, offset)
    record_rbdapi_test('Image.write', ret, id(data), offset)
    print('write data to image[' + str(offset) + ':+' + str(len(data)) + ']')

def clone_image(p_ioctx, p_image, p_snap, c_ioctx, c_image):
    ret = RBD().clone(p_ioctx, p_image, p_snap, c_ioctx, c_image)
    record_rbdapi_test('RBD.clone', ret, Ioctx_obj_to_dict(p_ioctx), p_image, p_snap, Ioctx_obj_to_dict(c_ioctx), c_image)
    print('clone image: ' + p_image + '@' + p_snap + ' -> ' + c_image)

@mytimeit
def create_snap(image, snapname):
    ret = image.create_snap(snapname)
    record_rbdapi_test('image.create_snap', ret, snapname)
    print('create snap ' + snapname)

@mytimeit
def remove_snap(image, snapname):
    ret = image.remove_snap(snapname)
    record_rbdapi_test('image.remove_snap', ret, snapname)
    print('remove snap ' + snapname)

@mytimeit
def create_snap_with_open_img(ioctx, imagename, snapname):
    image = open_image(ioctx, imagename)
    ret = image.create_snap(snapname)
    close_image(image)
    record_rbdapi_test('image.create_snap', ret, snapname)
    print('create snap ' + snapname)

@mytimeit
def remove_snap_with_open_img(ioctx, imagename, snapname):
    image = open_image(ioctx, imagename)
    ret = image.remove_snap(snapname)
    close_image(image)
    record_rbdapi_test('image.remove_snap', ret, snapname)
    print('remove snap ' + snapname)

def list_snaps(image):
    snaplist = image.list_snaps()
    record_rbdapi_test('image.list_snaps', SnapIterator_obj_to_dict(snaplist))
    print('list snaps')
    return snaplist

def rollback_to_snap(image, snapname):
    ret = image.rollback_to_snap(snapname)
    record_rbdapi_test('Image.rollback_to_snap', ret, snapname)
    print('rollback to snap: ' + snapname)

def set_snap(image, snapname):
    ret = image.set_snap(snapname)
    record_rbdapi_test('Image.set_snap', ret, snapname)
    print('set snap: ' + snapname)

def rename_snap(image, old, new):
    ret = image.rename_snap(old, new)
    record_rbdapi_test('Image.rename_snap', ret, old, new)
    print('rename snap: ' + old + ' -> ' + new)

def protect_snap(image, snapname):
    ret = image.protect_snap(snapname)
    record_rbdapi_test('Image.protect_snap', ret, snapname)
    print('protect snap ' + snapname)

def unprotect_snap(image, snapname):
    ret = image.unprotect_snap(snapname)
    record_rbdapi_test('Image.unprotect_snap', ret, snapname)
    print('unprotect snap ' + snapname)
    return ret

def is_protected_snap(image, snapname):
    ret = image.is_protected_snap(snapname)
    record_rbdapi_test('Image.is_protected_snap', ret, snapname)
    print('snap ' + snapname + ' is_protected: ' + str(ret))
    return ret

def usage():
    print(
    """
Welcome to use rbd-apitest!
Usage: python test_rbdapi.py [-c|--config config] [-h|--help] [-v|--version]
    -h or --help:               show this usage info
    -c or --config:             assigne config file
    -d or --diff:               diff file
    -o or --output:             output file
    -v or --version:            show version
    """
    )

def args_parse():
    opts = ''
    try:
        shorts = 'd:c:o:hv'
        longs = ['diff=','config=','output=','help','version']
        opts, args = getopt.getopt(sys.argv[1:], shorts, longs) 
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    
    for ckey, arg in opts: 
        if ckey in ("-h", "--help"):
            usage()
            sys.exit()
        elif ckey in ("-c", "--config"):
            global conf_file
            conf_file = arg
        elif ckey in ("-o", "--output"):
            global output_file
            output_file = arg
        elif ckey in ("-d", "--diff"):
            global do_diff_result
            do_diff_result = True
            global diff_file
            diff_file = arg
        elif ckey in ("-v", "--version"):
            print("%s version 1.0" % sys.argv[0])

def test_start():
    try:
        global conf_file
        cluster = connect_cluster(conf_file)
        get_cluster_fsid(cluster)
        try:
            poolname1 = get_temp_pool_name()
            pdb.set_trace()
            create_pool(cluster, poolname1)
            ioctx = open_pool(cluster, poolname1)
            try:
                features = init_features()
                imagename1 = get_temp_image_name()
                create_image(ioctx, imagename1, features)
                image = open_image(ioctx, imagename1)
                try:
                    #data = rand_data(1024)
                    #write_data_to_image(image, data, 0)
                    #flush_image(image)
                    snapname1 = get_temp_snap_name()
                    create_snap(image,snapname1)
                    remove_snap(image, snapname1)
                finally:
                    close_image(image)
                remove_image(ioctx, imagename1)
            finally:
                close_pool(ioctx)
                delete_pool(cluster, poolname1)
        finally:
            get_cluster_stats(cluster)
            poollist = list_pools(cluster)
    finally:
        shutdown_cluster(cluster)



import time, threading


def loop(times, concurrency):
  i = 0
  while i < times:
    print("thread :%s is running..." % threading.current_thread().name)
    n = 0
    while n < concurrency:
      n = n + 1
      print("thread %s >>> %s" % (threading.current_thread().name, n))
      time.sleep(1)
    print("thread %s ended." % threading.current_thread().name)
    i = i + 1

@mytimeit
def test_loop():
    #t = threading.Thread(target=loop(1, 150), name='LoopThread')
    t = threading.Thread(target=loop(1, 3), name='LoopThread')
    t.start()
    t.join()
    print("thread %s ended." % threading.current_thread().name)

@mytimeit
def test_create_and_delete_image():
    try:
        global conf_file
        cluster = connect_cluster(conf_file)
        try:
            poolname1 = "test-pool-001" 
            create_pool(cluster, poolname1)
            ioctx = open_pool(cluster, poolname1)
            try:
                features = init_features()
                imagename1 = "test-image-001"
                create_image(ioctx, imagename1, features)
                image = open_image(ioctx, imagename1)
                try:
                    #data = rand_data(1024)
                    #write_data_to_image(image, data, 0)
                    #flush_image(image)
                    snapname1 = "test-snap-001"
                    create_snap(image,snapname1)
                    remove_snap(image, snapname1)
                finally:
                    close_image(image)
                remove_image(ioctx, imagename1)
            finally:
                close_pool(ioctx)
        finally:
            get_cluster_stats(cluster)
            delete_pool(cluster, poolname1)
    finally:    
        shutdown_cluster(cluster)

@mytimeit
def init_resource():
    global conf_file
    cluster = connect_cluster(conf_file)
    #global pool_name 
    create_pool(cluster, pool_name)
    global ioctx 
    ioctx = open_pool(cluster, pool_name)
    global features
    features = init_features()
    get_cluster_stats(cluster)

@mytimeit
def delete_resource():
    try:
        global conf_file
        cluster = connect_cluster(conf_file)
        close_pool(ioctx)
        get_cluster_stats(cluster)
        delete_pool(cluster, pool_name)
    finally:    
        shutdown_cluster(cluster)

@mytimeit
def test_resource():
    init_resource()
    delete_resource()

@mytimeit
def test_create_images(thread_num, ioctx, features):
    print("begin test_create_images===")
    start_time = time.time()
    n = 0
    thread_list = []
    while n < thread_num:
        tmp_imagename = get_temp_image_name()
        t = threading.Thread(target=create_image, args=(ioctx, tmp_imagename, features))
        t.start()
        print("tmp_imagename:%s thread_name:%s started", tmp_imagename, t.getName())
        thread_list.append(t)
        n = n + 1
    for t in thread_list:
        t.join()
    print(">>>>>thread_list all joined:%s", thread_list)
    end_time = time.time()
    print("%s函数平均运行时间为：%.2f" %('avg_test_create_images', (end_time - start_time)/(thread_num)))
    print("end test_create_images------------")

@mytimeit
def test_remove_images(thread_num, ioctx):
    start_time = time.time()
    n = 0
    thread_list = []
    while n < thread_num:
        tmp_imagename = get_temp_image_name_cur()
        t = threading.Thread(target=remove_image, args=(ioctx, tmp_imagename))
        t.start()
        thread_list.append(t)
        n = n + 1
    for t in thread_list:
        t.join()
    end_time = time.time()
    print("%s函数平均运行时间为：%.2f" %('avg_test_remove_images', (end_time - start_time)/(thread_num)))

@mytimeit
def test_create_snapshots(thread_num, ioctx):
    start_time = time.time()
    n = 0
    thread_list = []
    while n < thread_num:
        tmp_snapname = get_temp_snap_name()
        tmp_imagename = get_temp_image_name_cur()
        t = threading.Thread(target=create_snap_with_open_img, args=(ioctx, tmp_imagename, tmp_snapname))
        t.start()
        thread_list.append(t)
        n = n + 1
    for t in thread_list:
        t.join()
    end_time = time.time()
    print("%s函数平均运行时间为：%.2f" %('avg_test_create_snapshots', (end_time - start_time)/(thread_num)))

@mytimeit
def test_remove_snapshots(thread_num, ioctx):
    start_time = time.time()
    n = 0
    thread_list = []
    while n < thread_num:
        # tmp_imagename = '%s-%s-%s' % (imagename, i, n)
        # # image = open_image(ioctx, tmp_imagename)
        # tmp_snapname = '%s-%s-%s' % (snapname, i, n)
        tmp_snapname = get_temp_snap_name_cur()
        tmp_imagename = get_temp_image_name()
        t = threading.Thread(target=remove_snap_with_open_img, args=(ioctx, tmp_imagename, tmp_snapname))
        t.start()
        thread_list.append(t)
        # close_image(image)
        n = n + 1
    for t in thread_list:
        t.join()
    end_time = time.time()
    print("%s函数平均运行时间为：%.2f" %('avg_test_remove_snapshots', (end_time - start_time)/(thread_num)))

@mytimeit
def main_test():
    from functools import partial
    init_resource()
    times = 1
    thread_num = 150
    try:
        times_res = timeit.timeit(
            stmt=partial(test_create_images, thread_num, ioctx, features),
            number=times)
    finally:
        print("test_create_images:%s", times_res)
        times_res = timeit.timeit(
            stmt=partial(test_create_snapshots, thread_num, ioctx),
            number=times)
        print("test_create_snapshots:%s", times_res)
        times_res = timeit.timeit(
            stmt=partial(test_remove_snapshots, thread_num, ioctx),
            number=times)
        print("test_remove_snapshots:%s", times_res)
        times_res = timeit.timeit(
            stmt=partial(test_remove_images, thread_num, ioctx),
            number=times)
        print("test_remove_images:%s", times_res)
        delete_resource()
    # test_create_images(thread_num, ioctx, features)
    # test_create_snapshots(thread_num, ioctx)
    # test_remove_snapshots(thread_num, ioctx)
    # test_remove_images(thread_num, ioctx)

if __name__ == "__main__":
    #test_loop()
    #test_start()
    #test_create_and_delete_image()
    #test_create_and_delete_image()
    #test_resource()

    init_output_file()
    main_test()
    write_output_info()
    sys.exit()
