import argparse
import os
import sys
import gym
import config
import copy
import time
import numpy as np
import subprocess

parser = argparse.ArgumentParser(description="Run commands")

def new_tmux_cmd(session, name, cmd):
    if isinstance(cmd, (list, tuple)):
        cmd = " ".join(str(v) for v in cmd)
    return name, "tmux send-keys -t {}:{} '{}' Enter".format(session, name, cmd)


def create_tmux_commands(session, logdir):

    '''
    Coder: YuhangSong
    Description: specific sequence of games to run
    '''

    '''for launching the TF workers'''
    from config import project, mode
    '''different from f on_line and others'''
    if (project is 'f') and (mode is 'on_line'):

        '''genrate game done dic for first run, so that latter is auto started by the programe'''
        done_sinal_dic = []
        worker_running = 0
        for game_i in range(0,len(config.game_dic)):
            for subjects_i in range(0,config.num_subjects):
                done_sinal_dic += [[game_i,subjects_i]]
                worker_running += 1
                if worker_running >= config.num_workers_one_run:
                    breakout = True
                    break
            if breakout:
                break

        from config import worker_done_signal_dir, worker_done_signal_file
        '''clean the temp dir'''
        subprocess.call(["rm", "-r", worker_done_signal_dir])
        subprocess.call(["mkdir", "-p", worker_done_signal_dir])
        '''save the done_sinal_dic'''
        np.savez(worker_done_signal_dir+worker_done_signal_file,
                 done_sinal_dic=done_sinal_dic)

        '''cmds for init the tmux session'''
        cmds = [
            "mkdir -p {}".format(logdir),
            "tmux kill-session -t {}".format(session),
            "tmux new-session -s {} -d".format(session),
        ]

        return cmds
    else:
        base_cmd = [
            'CUDA_VISIBLE_DEVICES=', sys.executable, 'worker.py',
            '--log-dir', logdir, '--env-id', config.game_dic[0],
            '--num-workers', str(config.num_workers_total_global)]

        '''main cluster has ps worker'''
        if(config.cluster_current==config.cluster_main):
            cmds_map = [new_tmux_cmd(session, "ps", base_cmd + ["--job-name", "ps"])]
        else:
            cmds_map = []

        for i in range(config.num_workers_total_global):
            if((i % config.num_workers_global) >= config.num_workers_local):
                continue
            base_cmd = [
                'CUDA_VISIBLE_DEVICES=', sys.executable, 'worker.py',
                '--log-dir', logdir,
                '--env-id', config.game_dic[i / config.num_workers_global],
                '--num-workers', str(config.num_workers_total_global)]
            cmds_map += [new_tmux_cmd(session,
                                      "w-%d" % i,
                                      base_cmd + ["--job-name", "worker",
                                                  "--task", str(i+config.task_plus)])]

        windows = [v[0] for v in cmds_map]

        cmds = [
            "mkdir -p {}".format(logdir),
            "tmux kill-session -t {}".format(session),
            "tmux new-session -s {} -n {} -d".format(session, windows[0]),
        ]
        for w in windows[1:]:
            cmds += ["tmux new-window -t {} -n {}".format(session, w)]
        cmds += ["sleep 1"]
        for window, cmd in cmds_map:
            cmds += [cmd]

        return cmds

def create_tmux_commands_auto(session, logdir, worker_running, game_i_at, subject_i_at):

    ''''''
    cmds_map = []

    if (game_i_at>=len(config.game_dic)) or (subject_i_at>=config.num_subjects):
        print('all done')
        print(s)

    '''scan'''
    for game_i in range(game_i_at,len(config.game_dic)):
        for subjects_i in range(subject_i_at,config.num_subjects):

            '''first thing, check if worker_running is full, if not go on to create_tmux_commands_auto'''
            breakout = False
            if worker_running >= config.num_workers_one_run:
                subject_i_at = subjects_i
                breakout = True
                break

            base_cmd = [
                'CUDA_VISIBLE_DEVICES=', sys.executable, 'worker.py',
                '--log-dir', logdir, '--env-id', config.game_dic[game_i],
                '--num-workers', str(1)]

            cmds_map += [new_tmux_cmd(session, 'g-'+str(game_i)+'-s-'+str(subjects_i)+'-ps', base_cmd + ["--job-name", "ps",
                                                                                                         "--subject", str(subjects_i)])]

            base_cmd = [
                'CUDA_VISIBLE_DEVICES=', sys.executable, 'worker.py',
                '--log-dir', logdir,
                '--env-id', config.game_dic[game_i],
                '--num-workers', str(1)]
            cmds_map += [new_tmux_cmd(session,
                                      'g-'+str(game_i)+'-s-'+str(subjects_i)+'-w-0',
                                      base_cmd + ["--job-name", "worker",
                                                  "--task", str(0),
                                                  "--subject", str(subjects_i)])]

            '''created new worker, add worker_running'''
            print('a pair of ps_worker for game '+config.game_dic[game_i]+' subject '+str(subjects_i)+' is created.')
            worker_running += 1

        if breakout:
            game_i_at = game_i
            break

    '''see if cmd added'''
    if len(cmds_map) > 0:

        ''''''
        windows = [v[0] for v in cmds_map]
        cmds = []
        for w in windows:
            cmds += ["tmux new-window -t {} -n {}".format(session, w)]
        cmds += ["sleep 1"]
        for window, cmd in cmds_map:
            cmds += [cmd]

        '''excute cmds'''
        os.system("\n".join(cmds))

    return worker_running, game_i_at, subject_i_at

def kill_a_pair_of_ps_worker_windows(session,game,subject):

    print('a pair of ps_worker for game '+config.game_dic[game]+' subject '+str(subject)+' is being killed.')

    '''ganerate cmds'''
    cmds = []
    cmds += ["tmux kill-window -t "+session+":"+"g-"+str(game)+"-s-"+str(subject)+"-w-"+str(0)]
    cmds += ["tmux kill-window -t "+session+":"+"g-"+str(game)+"-s-"+str(subject)+"-ps"]

    '''excute cmds'''
    os.system("\n".join(cmds))

def run():

    args = parser.parse_args()
    session = "a3c"

    cmds = create_tmux_commands(session, config.final_log_dir)
    print("\n".join(cmds))
    os.system("\n".join(cmds))

    from config import project, mode
    if (project is 'f') and (mode is 'on_line'):

        '''auto worker starter'''

        '''init position recorder'''
        worker_running = config.num_workers_one_run # this is fake to start the run
        game_i_at=0
        subject_i_at=0

        '''detecting'''
        while True:

            # print('checking if any worker done')

            from config import worker_done_signal_dir, worker_done_signal_file
            '''load done_sinal_dic'''
            done_sinal_dic = np.load(worker_done_signal_dir+worker_done_signal_file)['done_sinal_dic']

            '''clear the done_sinal_dic'''
            np.savez(worker_done_signal_dir+worker_done_signal_file,
                     done_sinal_dic=[[-1,-1]])

            '''scan done_sinal_dic, kill windows according to done_sinal_dic'''
            for i in range(np.shape(done_sinal_dic)[0]):

                '''if done_sinal_dic signal is -1, it is putted in by the control and it is invalid'''
                if done_sinal_dic[i][0] < 0:
                    continue

                '''kill_a_pair_of_ps_worker_windows'''
                kill_a_pair_of_ps_worker_windows(session,done_sinal_dic[i][0],done_sinal_dic[i][1])
                '''refresh the worker_running'''
                worker_running -= 1

            '''refresh to see if any thing need to create'''
            worker_running, game_i_at, subject_i_at = create_tmux_commands_auto(session, config.final_log_dir, worker_running, game_i_at, subject_i_at)

            '''sleep for we do not need to detecting very frequent'''
            time.sleep(config.check_worker_done_time)


if __name__ == "__main__":
    run()
