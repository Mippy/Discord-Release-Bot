import discord
from discord.ext import commands
from datetime import datetime
import time
import json
import asyncio
import requests
import re
import os

with open('config.json') as fp:
    data = json.load(fp)
    cuid = data['client_id']
    token = data['token']
    prefix = data['prefix']
    owner = data['owner_id']

def get_build_info(channel):
    if channel != 'stable':
        url = f'https://{channel}.discordapp.com/'
    else:
        url = 'https://discordapp.com/'
    r = requests.get(url + 'app')
    build_id = r.headers['x-build-id']
    data = r.text.split('<script src="/assets/')[3].split('"')[0] # get the JS file
    r = requests.get(url + 'assets/' + data)
    regex = re.compile('Build Number: [0-9]+, Version Hash: [A-Za-z0-9]+')
    build_strings = regex.findall(r.text)[0].replace('Build Number: ', '').split(',')
    bs = [build_strings[0], [build_strings[1].replace(' Version Hash: ', '')]]
    return {"build_id": build_id, "build_number": bs[0], "build_hash": bs[1][0]}

def get_latest(v=None):
    channels = ['stable', 'ptb', 'canary']
    for channel in channels:
        build_info = get_build_info(channel)
        build_number = build_info['build_number']
        if channel == 'stable':
            stable = int(build_number)
            stablebi = build_info
        elif channel == 'ptb':
            ptb = int(build_number)
            ptbbi = build_info
        else:
            canary = int(build_number)
            canarybi = build_info
    def get_indiv_latest():
        if stable >= ptb and stable >= canary:
            return [stablebi, 'stable']
        if ptb >= stable and ptb >= canary:
            return [ptbbi, 'ptb']
        if canary >= stable and canary >= ptb:
            return [canarybi, 'canary']
    if v == 'all':
        return {"stable": stablebi, "ptb": ptbbi, "canary": canarybi, "latest": get_indiv_latest()}
    return get_indiv_latest()

async def notify(channel, info):
    channel = channel.capitalize()
    if channel == 'Ptb':
        channel = 'PTB'
    e = discord.Embed(color=discord.Color.blurple(), title=f'New {channel} Update')
    e.timestamp = datetime.utcnow()
    e.set_footer(text=f'You received this because you are subscribed for {channel} alerts. Unsubscribe with {prefix}subscribe {channel}.')
    e.add_field(name='Build Number', value=info['build_number'], inline=False)
    e.add_field(name='Build Hash', value=info['build_hash'], inline=False)
    e.add_field(name='Build ID', value=info['build_id'], inline=False)
    with open('data.json') as fp:
        content = json.load(fp)
        subs = content['subscriptions']
        for k, v in subs.items():
            if v[channel.lower()] == 1:
                user = bot.get_user(int(k))
                try:
                    await user.send(embed=e)
                except: pass

bot = commands.AutoShardedBot(command_prefix=commands.when_mentioned_or(prefix), case_insensitive=True, activity=discord.Game(name='starting up. please wait...'), status=discord.Status.idle)
bot.remove_command('help')
channels = ['stable', 'ptb', 'canary']

global latest
latest = get_latest(v='all')

async def check_for_updates():
    global latest
    while True:
        for channel in channels:
            uri = f'https://{channel}.discordapp.com/app'
            if channel == 'stable':
                uri = 'https://discordapp.com/app'
            bir = requests.get(uri)
            build_id = bir.headers['x-build-id']
            with open('data.json', 'r+') as fp:
                content = json.load(fp)
                if content['history'][channel][0]['build_id'] != build_id:
                    gbi = get_build_info(channel)
                    latest[channel] = gbi
                    if latest['stable']["build_number"] >= latest['ptb']["build_number"] and latest['stable']["build_number"] >= latest['canary']["build_number"]:
                        l = 'stable'
                    elif latest['ptb']["build_number"] >= latest['stable']["build_number"] and latest['ptb']["build_number"] >= latest['canary']["build_number"]:
                        l = 'ptb'
                    elif latest['canary']["build_number"] >= latest['stable']["build_number"] and latest['canary']["build_number"] >= latest['ptb']["build_number"]:
                        l = 'canary'
                    await bot.change_presence(activity=discord.Game(name=f'latest build {latest[l]["build_number"]} ({l})'), status=discord.Status.online)
                    content['history'][channel].insert(0, gbi)
                    fp.seek(0)
                    json.dump(content, fp)
                    fp.truncate()
                    await notify(channel, latest[channel])
        await asyncio.sleep(30)

@bot.event
async def on_ready():
    platest = latest['latest']
    await bot.change_presence(activity=discord.Game(name=f'latest build {platest[0]["build_number"]} ({platest[1]})'), status=discord.Status.online)
    await check_for_updates()

@bot.command(name='help', aliases=['cmds', 'commands'])
async def help_cmd(ctx):
    e = discord.Embed(color=discord.Color.blurple(), title='Commands List')
    e.description = '`{0}help` | Show this list.\n`{0}ping` | Show the ping.\n`{0}info` | Show information about this bot.\n`{0}subscribe` | Subscribe to get notifications when there\'s a new release.\n`{0}latest` | Show the current latest versions for all release channels.\n`{0}stable` | Show information about the Stable release channel.\n`{0}ptb` | Show information about the PTB release channel.\n`{0}canary` | Show information about the Canary release channel.'.format(prefix)
    e.timestamp = datetime.utcnow()
    try:
        await ctx.author.send(embed=e)
        if ctx.guild:
            await ctx.send(f'{ctx.author.mention}, check your DMs for a message from me.')
    except:
        await ctx.send(f'{ctx.author.mention}, for some reason I couldn\'t send you a DM. Make sure your Privacy settings are correct.')

@bot.command(name='shutdown')
async def shutdown_cmd(ctx, mode=None):
    if ctx.author.id == int(owner):
        if not mode:
            return await ctx.send(f'{ctx.author.mention}:\nUsage: `{prefix}shutdown <-s(hutdown) | -r(estart) | -u(pdate)>`')
        if mode == '-s':
            await ctx.send(f'{ctx.author.mention}, shutting down...')
            await bot.logout()
        if mode == '-r':
            await ctx.send(f'{ctx.author.mention}, restarting...')
            os.system('python3.6 bot.py &')
            await bot.logout()
        if mode == '-u':
            await ctx.send(f'{ctx.author.mention}, updating, then restarting...')
            os.system('git pull')
            os.system('python3.6 bot.py &')
            await bot.logout()

@bot.command(name='ping')
async def ping_cmd(ctx):
    t1 = time.perf_counter()
    message = await ctx.send("Checking the ping... :cd:")
    t2 = time.perf_counter()
    await message.delete()
    ping = round((t2-t1)*1000)
    await ctx.send(":ping_pong: **Pong,** `{}`** ms!**".format(ping))

@bot.command(name='info')
async def info_cmd(ctx):
    e = discord.Embed(color=discord.Color.blurple(), title='Discord#1337', description='Created by Isabel#0002')
    e.timestamp = datetime.utcnow()
    e.set_footer(text=f'Requested by {ctx.author} ({ctx.author.id})')
    e.add_field(name='The Bot', value='The purpose of the bot is for reporting new releases across all release channels of Discord.')
    e.add_field(name='Thanks to:', value='- [Discord](https://discordapp.com)\n- [discord.py](https://discord.gg/r3sSKJJ)\n- [Discord API Community](https://discord.gg/discord-api)\n- [Discord Testers Community](https://discord.gg/discord-testers)\n- [The Discord Wiki](https://discordia.me)')
    e.add_field(name='Invite', value='[Invite Link](https://discordapp.com/api/oauth2/authorize?client_id=323575234005303296&permissions=19456&scope=bot)')
    try:
        await ctx.send(embed=e)
    except discord.Forbidden:
        await ctx.send('It seems I cannot send the output. Please allow me `Embed Links`.')

@bot.command(name='latest')
async def latest_cmd(ctx):
    e = discord.Embed(color=discord.Color.blurple(), title='Latest Version')
    e.timestamp = datetime.utcnow()
    e.set_footer(text=f'Requested by {ctx.author} ({ctx.author.id})')
    for channel in channels:
        if channel == 'ptb':
            title = 'PTB'
        else:
            title = channel.capitalize()
        build_number = latest[channel]['build_number']
        build_hash = latest[channel]['build_hash']
        build_id = latest[channel]['build_id']
        e.add_field(name=title, value=f'Build Number: {build_number}\nBuild Hash: {build_hash}\nBuild ID: {build_id}', inline=False)
    try:
        await ctx.send(embed=e)
    except discord.Forbidden:
        await ctx.send('It seems I cannot send the output. Please allow me `Embed Links`.')

@bot.command(name='canary')
async def canary_cmd(ctx):
    e = discord.Embed(color=discord.Color.blurple(), title='Canary')
    e.timestamp = datetime.utcnow()
    e.set_footer(text=f'Requested by {ctx.author} ({ctx.author.id})')
    build_info = latest['canary']
    e.description = 'Canary is Discord\'s alpha testing program. It\'s very unstable and has a lot of bugs, but usually gets features earlier than the PTB or Stable clients. The Canary Build\'s purpose is to allow users to help Discord test new features.' # source: https://discordia.me/canary
    e.add_field(name='Current Version', value=f'Build Number: {build_info["build_number"]}\nVersion Hash: {build_info["build_hash"]}\nBuild ID: {build_info["build_id"]}')
    dl_url = 'https://discordapp.com/api/download/canary?platform='
    e.add_field(name='Download', value=f'[Windows]({dl_url+"win"})\n[macOS]({dl_url+"osx"})\n[Linux deb]({dl_url+"linux&format=deb"})\n[Linux tar.gz]({dl_url+"linux&format=tar.gz"})', inline=False)
    try:
        await ctx.send(embed=e)
    except discord.Forbidden:
        await ctx.send('It seems I cannot send the output. Please allow me `Embed Links`.')

@bot.command(name='ptb')
async def ptb_cmd(ctx):
    e = discord.Embed(color=discord.Color.blurple(), title='PTB')
    e.timestamp = datetime.utcnow()
    e.set_footer(text=f'Requested by {ctx.author} ({ctx.author.id})')
    build_info = latest['ptb']
    e.description = 'The Public Test Build is the beta version of the Discord Client and the middle ground between the Stable and Canary clients. The Public Test Build (PTB) sometimes has features that are not available on Stable. The PTB is intended to be a way for users to help Discord test new features, so it can be expected that PTB is less stable than the main client. PTB tends to receive features later than the Canary build.' # source: https://discordia.me/ptb
    e.add_field(name='Current Version', value=f'Build Number: {build_info["build_number"]}\nVersion Hash: {build_info["build_hash"]}\nBuild ID: {build_info["build_id"]}')
    dl_url = 'https://discordapp.com/api/download/ptb?platform='
    e.add_field(name='Download', value=f'[Windows]({dl_url+"win"})\n[macOS]({dl_url+"osx"})\n[Linux deb]({dl_url+"linux&format=deb"})\n[Linux tar.gz]({dl_url+"linux&format=tar.gz"})', inline=False)
    try:
        await ctx.send(embed=e)
    except discord.Forbidden:
        await ctx.send('It seems I cannot send the output. Please allow me `Embed Links`.')

@bot.command(name='stable')
async def stable_cmd(ctx):
    e = discord.Embed(color=discord.Color.blurple(), title='Stable')
    e.timestamp = datetime.utcnow()
    e.set_footer(text=f'Requested by {ctx.author} ({ctx.author.id})')
    build_info = latest['stable']
    e.description = 'Discord Stable is the main Discord client. The main client is called Stable because it has very little bugs. All features released on stable have been tested for bugs by users on Canary and/or the Public Test Build (PTB).' # source: https://discordia.me/stable
    e.add_field(name='Current Version', value=f'Build Number: {build_info["build_number"]}\nVersion Hash: {build_info["build_hash"]}\nBuild ID: {build_info["build_id"]}')
    dl_url = 'https://discordapp.com/api/download/stable?platform='
    e.add_field(name='Download', value=f'[Windows]({dl_url+"win"})\n[macOS]({dl_url+"osx"})\n[Linux deb]({dl_url+"linux&format=deb"})\n[Linux tar.gz]({dl_url+"linux&format=tar.gz"})', inline=False)
    try:
        await ctx.send(embed=e)
    except discord.Forbidden:
        await ctx.send('It seems I cannot send the output. Please allow me `Embed Links`.')

@bot.command(name='subscribe')
async def subscribe_cmd(ctx, *, feeds=None):
    if not feeds:
        e = discord.Embed(color=discord.Color.blurple(), title='Your Subscriptions', description=f'Subscribe to receive a message when there\'s a new release to a channel. `{prefix}subscribe <channel(s), can be comma separated.>`')
        e.set_footer(text=f'Requested by {ctx.author} ({ctx.author.id})')
        e.timestamp = datetime.utcnow()
        with open('data.json') as fp:
            stable = 'Not Subscribed'
            ptb = 'Not Subscribed'
            canary = 'Not Subscribed'
            content = json.load(fp).get('subscriptions')
            content = content.get(str(ctx.author.id))
            if content:
                if content.get('stable') == 1:
                    stable = 'Subscribed'
                if content.get('ptb') == 1:
                    ptb = 'Subscribed'
                if content.get('canary') == 1:
                    canary = 'Subscribed'
            e.add_field(name='Stable', value=stable, inline=False)
            e.add_field(name='PTB', value=ptb, inline=False)
            e.add_field(name='Canary', value=canary, inline=False)
        try:
            await ctx.send(embed=e)
        except:
            await ctx.send('It seems I cannot send the output. Please allow me `Embed Links`.')
    else:
        feeds = feeds.lower().replace(' ', '').replace(',', ' ').split(' ')
        pfeeds = []
        for channel in channels:
            if channel in feeds:
                pfeeds.append(1)
            else:
                pfeeds.append(0)
        with open('data.json', 'r+') as fp:
            initcontent = json.load(fp)
            content = initcontent.get('subscriptions').get(str(ctx.author.id))
            if not content:
                initcontent['subscriptions'][str(ctx.author.id)] = {"stable": pfeeds[0], "ptb": pfeeds[1], "canary": pfeeds[2]}
                fp.seek(0)
                json.dump(initcontent, fp)
                fp.truncate()
            else:
                i = 0
                for channel in channels:
                    if pfeeds[i] == initcontent['subscriptions'][str(ctx.author.id)][channel]:
                        if pfeeds[i] == 1:
                            initcontent['subscriptions'][str(ctx.author.id)][channel] = 0
                    else:
                        initcontent['subscriptions'][str(ctx.author.id)][channel] = 1
                    i += 1
                fp.seek(0)
                json.dump(initcontent, fp)
                fp.truncate()
        await ctx.send(f'{ctx.author.mention}, your subscriptions have been updated successfully.')

bot.run(token)
