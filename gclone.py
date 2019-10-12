#!/usr/bin/env python3

from __future__ import print_function
import sys
import readline
from os import environ
import subprocess
import os
from urllib.request import Request, urlopen
import json
from pathlib import Path
import yaml
from collections import OrderedDict
import argparse

def represent_dictionary_order(self, dict_data):
    return self.represent_mapping('tag:yaml.org,2002:map', dict_data.items())

def setup_yaml():
    yaml.add_representer(OrderedDict, represent_dictionary_order)

setup_yaml()    

home = str(Path.home())
config_path = ('%s/%s')%(home,'.config/gclone.yaml')
cache_path = ('%s/%s')%(home,'.cache/gclone_cache.yaml')

endpoint = 'https://api.github.com/users'
headers = {'Accept': 'application/vnd.github.v3+json'}

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

default_config = OrderedDict({'allways_update_cache': False, 'default_user': 'rostegg'})

def read_config():
    try:
        with open(config_path, 'r') as config_stream:
            try:
                return { **default_config, **yaml.safe_load(config_stream)}
            except yaml.YAMLError:
                print("%s[!] Can't open local config file, seems it corrupted, creating new...%s"%(Colors.FAIL, Colors.ENDC))
                create_config(default_config)
                return default_config
    except FileNotFoundError:
        print("%s[!] Default config file not found, creating new...%s"%(Colors.WARNING, Colors.ENDC))
        create_config(default_config)
        return default_config        

def create_config(config_data):
    with open(config_path, 'w') as file:
        file.write(yaml.dump(config_data))

cfg = read_config()

def git_status():
    try:
        with open(os.devnull, 'w') as null:
            proc = subprocess.Popen("git", stdout=null, stderr=null)
            proc.communicate()
        return True
    except OSError:
        return False

if (not(git_status())):
    print("%s[!] Seems, like git not installed..%s"%(Colors.FAIL, Colors.ENDC))
    exit(1)

def clone_repository(url):
    try:
        subprocess.check_output(["git", "clone", url])
    except subprocess.CalledProcessError:
        print("%s[!] Error occured, while cloning repository..%s"%(Colors.FAIL, Colors.ENDC))
        exit(1)

parser = argparse.ArgumentParser()
parser.add_argument("--update-cache", help="update cached repositories list",
                    action="store_true")
parser.add_argument("--clear-cache", help="delete cached repositories list",
                    action="store_true")
parser.add_argument("--clear-config", help="delete config file",
                    action="store_true")
parser.add_argument("--user", help="github username",
                    action="store")
parser.add_argument("--set-user", help="set github username global",
                    action="store")

args = parser.parse_args()

if (args.set_user):
    cfg['default_user'] = args.set_user
    create_config(cfg)
    os.remove(cache_path)
    print("%s[+] Created new config for %s%s%s"%(Colors.OKGREEN, Colors.OKBLUE, args.set_user, Colors.ENDC))
    exit(1)

# little bit ugly, but im fine with it
def remove_file(validator, path):
    try:
        validator and os.remove(path)
    except:
        pass

if (args.clear_cache or args.clear_config):
    remove_file(args.clear_cache, cache_path)
    remove_file(args.clear_config, config_path)
    args.clear_cache and print("%s[+] Cached repositories was succesfuly removed...%s"%(Colors.OKGREEN, Colors.ENDC))
    args.clear_config and print("%s[+] Config file was succesfuly removed...%s"%(Colors.OKGREEN, Colors.ENDC))
    exit(1)

current_user = args.user or cfg.get('default_user')
cache_update_require = True if args.user else (args.update_cache or cfg['allways_update_cache'])

def read_cache(user = current_user):
    if cache_update_require:
        return update_cache(user)
    try:
        with open(cache_path, 'r') as cache_stream:
            try:
                return OrderedDict(yaml.safe_load(cache_stream))
            except yaml.YAMLError:
                print("%s[!] Can't open local cache, seems it corrupted, creating new...%s"%(Colors.WARNING, Colors.ENDC))
                return update_cache(user)
    except FileNotFoundError:
        print("%s[!] Can't find local cache, retrieve repositories list from Github...%s"%(Colors.WARNING, Colors.ENDC))
        return update_cache(user)  

def get_repositories_list(user):
    url = ('%s/%s/repos?per_page=1000')%(endpoint,user)

    request = Request(url, headers=headers)
    try:
        response = urlopen(request).read()
    except:
        print("%s[!] Can't retrieve repositories list from Github...%s"%(Colors.FAIL,Colors.ENDC))
        exit(1)
    
    json_response = json.loads(response.decode('utf-8'))
    repositories_list = OrderedDict({ item['name']:item['git_url'] for item in json_response })
    return repositories_list

def write_to_cache(cache_data):
    with open(cache_path, 'w') as file:
        file.write(cache_data)

def update_cache(user):
    print("%s[+] Updating repositories list from Github...%s"%(Colors.OKGREEN,Colors.ENDC))
    cache = get_repositories_list(user)
    yaml_cache = yaml.dump(cache)
    write_to_cache(yaml_cache)
    return cache

repositories_cache = read_cache(current_user)

autocomple_dic = repositories_cache.keys()

class RepositoriesCompleter(object):
    
    def __init__(self, options):
        self.options = sorted(options)

    def complete(self, text, state):
        if state == 0:
            if not text:
                self.matches = self.options[:]
            else:
                self.matches = [s for s in self.options
                                if s and s.startswith(text)]
        try:
            return self.matches[state]
        except IndexError:
            return None

    def display_matches(self, substitution, matches, longest_match_length):
        line_buffer = readline.get_line_buffer()
        columns = environ.get("COLUMNS", 80)
        print()
        tpl = "{:<" + str(int(max(map(len, matches)) * 1.2)) + "}"
        buffer = ""
        for match in matches:
            match = tpl.format(match[len(substitution):])
            if len(buffer + match) > columns:
                print(buffer)
                buffer = ""
            buffer += match

        if buffer:
            print(buffer)

        print("> ", end="")
        print(line_buffer, end="")
        sys.stdout.flush()

def enter_repository():
    print('\nEnter repository name:\n\t')
    try:
        repository = input("> ")
    except KeyboardInterrupt:
        exit(1)
    try_clone(repository)

def try_clone(repository):
    url = repositories_cache.get(repository)
    if (not (url)):
        print("\n%s[!] Can't find repository in list, try again!%s"%(Colors.FAIL, Colors.ENDC))
        enter_repository()
    else:
        clone_repository(url)

def main():
    print()
    print("[+] Available repositories for %s%s%s:\n"%(Colors.OKBLUE, current_user, Colors.ENDC))
    print('\t' + '\n\t'.join('%s%s%s' % (Colors.BOLD, item, Colors.ENDC) for item in autocomple_dic))
    completer = RepositoriesCompleter(autocomple_dic)
    readline.set_completer_delims(' \t\n;')
    readline.set_completer(completer.complete)
    readline.parse_and_bind('tab: complete')
    readline.set_completion_display_matches_hook(completer.display_matches)
    enter_repository()

main()