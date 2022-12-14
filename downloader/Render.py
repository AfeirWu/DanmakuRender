import argparse
from datetime import datetime
import logging
import os
import queue
import subprocess
import sys
import threading
import multiprocessing
import asyncio
import time
from os.path import join


class Render():
    def __init__(self,args,ffmpeg:str='ffmpeg'):
        self.ffmpeg = ffmpeg
        self.args = args
        self.logger = logging.getLogger('render')
        self.stoped = False
        self.rendering = False

    def render(self,video,danmaku,output):
        ffmpeg_args = [self.ffmpeg]
        if self.args.hwaccel_args:
            hwaccel_args = self.args.hwaccel_args.split(',')
            ffmpeg_args += [*hwaccel_args]
        vencoder_args = self.args.vencoder_args.split(',')
        aencoder_args = self.args.aencoder_args.split(',')

        ffmpeg_args +=  [
                        '-i', video,
                        '-vf', 'subtitles=filename=%s'%danmaku.replace('\\','/'),

                        '-c:v',self.args.vencoder,
                        *vencoder_args,
                        '-c:a',self.args.aencoder,
                        *aencoder_args,

                        '-movflags','frag_keyframe',
                        output,
                        ]
        
        self.logger.debug('Danmaku Render args:')
        self.logger.debug(ffmpeg_args)

        if self.args.debug:
            proc = subprocess.Popen(ffmpeg_args, stdin=subprocess.PIPE, stdout=sys.stdout, stderr=subprocess.STDOUT,bufsize=10**8)
        else:
            proc = subprocess.Popen(ffmpeg_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,bufsize=10**8)

        return proc

    def auto_render(self,keyword,video_dir,dm_dir,output_dir,autoexit=False):
        self.stoped = False
        processed_files = []
        fsize_table = {}
        if autoexit:
            DELAY = 0
            t0 = 0
        else:
            DELAY = 45
            t0 = datetime.now().timestamp()-30
        
        while not self.stoped:
            video_list = []
            for f in os.listdir(video_dir):
                if keyword in f and f[-4:] != '.ass' and '??????' not in f:
                    if os.path.getctime(join(video_dir,f)) > t0:
                        video_list.append(f)
            unprocessed_files = sorted(list(set(video_list)-set(processed_files)))

            if len(unprocessed_files) == 0:
                if autoexit:
                    self.stop()
                else:
                    time.sleep(DELAY)
                continue
            
            for vname in unprocessed_files:
                vpath = join(video_dir,vname)
                file_size = fsize_table.get(vname,-1)
                if os.path.getsize(vpath) == file_size:
                    file_size = -1
                    dname = vname.replace('.mp4','.ass')
                    dpath = join(dm_dir,dname)
                    output = join(output_dir,vname.replace('-Part','(????????????)-Part'))
                    if not os.path.exists(dpath):
                        self.logger.info(f'??????{vpath}????????????????????????{dpath}???????????????.')
                        processed_files.append(vname)
                        continue
                    elif os.path.exists(output):
                        self.logger.info(f'???????????????????????????????????????{output}???????????????.')
                        processed_files.append(vname)
                        continue

                    self.logger.info(f'???????????? {vname}.')
                    self.rendering = True
                    self.render_proc = self.render(vpath,dpath,output)

                    if not self.args.debug:
                        info = None
                        log = ''
                        for line in self.render_proc.stdout.readlines():
                            try:
                                line = line.decode('utf-8').strip()
                            except UnicodeError as e:
                                self.logger.error(e)
                                self.logger.error(line)
                            log += line+'\n'
                            if line.startswith('video:'):
                                info = line
                        self.logger.debug(f'[Render Process]:{log}')
                        if info:
                            self.logger.info(f'{output} ????????????, {info}')
                        else:
                            self.logger.error(f'{output} ????????????:\n{log}')
                    else:
                        self.render_proc.wait()
                        
                    self.rendering = False
                    processed_files.append(vname)
                else:
                    fsize_table[vname] = os.path.getsize(vpath)
                
            time.sleep(DELAY)

    def stop(self):
        self.stoped = True
        if self.rendering:
            self.logger.warn(f"????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????? python main.py --render_only ????????????.")
            self.rendering = False
            try:
                out,_ = self.render_proc.communicate(b'q',2.0)
                out = out.decode('utf-8')
                self.logger.debug(out)
            except Exception as e:
                try:
                    self.render_proc.kill()
                except:
                    pass
                finally:
                    self.logger.debug(e)


