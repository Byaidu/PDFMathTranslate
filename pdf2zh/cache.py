import tempfile
import os
import time
import hashlib
import shutil

cache_dir = os.path.join(tempfile.gettempdir(), "cache")
os.makedirs(cache_dir, exist_ok=True)
time_filename = "update_time"
max_cache = 5


def deterministic_hash(obj):
    hash_object = hashlib.sha256()
    hash_object.update(str(obj).encode())
    return hash_object.hexdigest()[0:20]


def get_dirs():
    dirs = [
        os.path.join(cache_dir, dir)
        for dir in os.listdir(cache_dir)
        if os.path.isdir(os.path.join(cache_dir, dir))
    ]
    return dirs


def get_time(dir):
    try:
        timefile = os.path.join(dir, time_filename)
        t = float(open(timefile, encoding="utf-8").read())
        return t
    except FileNotFoundError:
        # handle the error as needed, for now we'll just return a default value
        return float(
            "inf"
        )  # This ensures that this directory will be the first to be removed if required


def write_time(dir):
    timefile = os.path.join(dir, time_filename)
    t = time.time()
    print(t, file=open(timefile, "w", encoding="utf-8"), end="")


def argmin(iterable):
    return min(enumerate(iterable), key=lambda x: x[1])[0]


def remove_extra():
    dirs = get_dirs()
    for dir in dirs:
        if not os.path.isdir(
            dir
        ):  # This line might be redundant now, as get_dirs() ensures only directories are returned
            os.remove(dir)
        try:
            get_time(dir)
        except BaseException:
            shutil.rmtree(dir)
    while True:
        dirs = get_dirs()
        if len(dirs) <= max_cache:
            break
        times = [get_time(dir) for dir in dirs]
        arg = argmin(times)
        shutil.rmtree(dirs[arg])


def is_cached(hash_key):
    dir = os.path.join(cache_dir, hash_key)
    return os.path.exists(dir)


def create_cache(hash_key):
    dir = os.path.join(cache_dir, hash_key)
    os.makedirs(dir, exist_ok=True)
    write_time(dir)


def load_paragraph(hash_key, hash_key_paragraph):
    filename = os.path.join(cache_dir, hash_key, hash_key_paragraph)
    if os.path.exists(filename):
        return open(filename, encoding="utf-8").read()
    else:
        return None


def write_paragraph(hash_key, hash_key_paragraph, paragraph):
    filename = os.path.join(cache_dir, hash_key, hash_key_paragraph)
    print(paragraph, file=open(filename, "w", encoding="utf-8"), end="")
