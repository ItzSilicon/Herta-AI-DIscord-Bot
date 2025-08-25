from typing import Literal
from random import random
from random import choice
from discord.ext import commands
import json
import cmds
import datetime
import logging
from asyncio import sleep
import discord
import sqlite3

logger=logging.getLogger(__name__)

def rate_choice(rate,a,b):
    r=random()
    if r>=rate:
        return a
    else:
        return b

def _recursive_access_data(data,args):
    if not data:
        return None
    if args:
        return _recursive_access_data(data,args)
    else:
        next_level=args.pop(0)
        try:
            data=data[next_level]
        except KeyError:
            data=data.get(next_level)
        except IndexError:
            return None
        return data
    
# def open_json(filename_no_dot_json,*args):
#     with open(f'{filename_no_dot_json}.json','r',encoding='utf-8') as fd:
#         data = json.load(fd)
#     return _recursive_access_data(data,args)

class player():
    def __init__(self,user_id):
        with open('hsr.json', "r",encoding="utf-8") as f:
            data=json.load(f)
            player=data.get(user_id)
        


class HSR_Pull(commands.Cog):
    def __init__(self,bot:commands.Bot):
        self.bot=bot
    def load_hsr_data(self):
        with open ('hsr.json','r',encoding='utf-8') as fd:
            hsr_data=json.load(fd)
        return hsr_data
    
    def write_hsr_data(self,uid,user_data:dict):
        with open ('hsr.json','r',encoding='utf-8') as fd:
            hsr_data=json.load(fd)
        try:
            hsr_data[uid]=user_data
        except Exception as e:
            return e
        with open('hsr.json','w',encoding='utf-8') as fd:
            json.dump(hsr_data,fd,indent=4,ensure_ascii=False)
        return
    
    def check_data(self,ctx:commands.Context,uid,hsr_data):
        base_data={
                "jade":16000.0,
                "pass":100,
                "special_pass":100,
                "last_request":cmds.now_l(),
                "characters":[],
                "light_cones":[],
                "auto_exchange":False,
                "warp_data":{},
                "counter":{},
                "pity_bools":{}
            }
        if uid not in hsr_data:
            hsr_data[str(uid)]=base_data
        else:
            for k,v in base_data.items():
                if k not in hsr_data[str(uid)]:
                    logger.info(f"user {ctx.author.name}'s data key {k} does not found, reset to {v}")
                    hsr_data[str(uid)][k]=v
                elif type(v) is not type(hsr_data[str(uid)][k]):
                    logger.info(f"user {ctx.author.name}'s data key {k} is corrupted, reset to {v}")
                    hsr_data[str(uid)][k]=v
            hsr_data['uid']=ctx.author.id
            hsr_data['name']=ctx.author.name
        return hsr_data
            
    
    @commands.command()
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def pull(self,ctx:commands.Context,number:str=None,amount=1):
        """崩壞：星穹鐵道模擬卡池
        Args:
            number (str): 卡池號碼，若未輸入則顯示所有可用卡池(包括過期卡池) Defaults to None.
            amount (Literal[1,10]): 抽數，只能單抽或十連抽 Defaults to 1.
        """
        if amount not in (1,10):
            await ctx.message.reply('只能單抽或十連抽，請輸入1或10。')
        # await ctx.message.reply("Hello,world!")

        logger.info(f'{ctx.author.name}(id:{ctx.author.id}) triggered pull command')
        uid=ctx.message.author.id
        hsr_data=self.load_hsr_data()
        hsr_data=self.check_data(ctx,str(uid),hsr_data)
        hsr_user=hsr_data[str(uid)]
        now=datetime.datetime.now()
        then=cmds.time_list_to_datetime(hsr_user['last_request'])
        diff:datetime.timedelta=now-then
        hsr_user['last_request']=cmds.now_l()
        hsr_user['jade']+=diff.seconds/60
        with open("warp.json",'r',encoding='utf-8') as fd:
            warp_data=json.load(fd)
        if not number:
            warp_list=[f"卡池號碼 {k}: {v.get('name')}" for k,v in warp_data.items()]
            lst='\n'.join(warp_list)
            await ctx.message.reply(f"請輸入卡池號碼，目前有以下卡池:\n{lst}")
            return
        warp_info=warp_data.get(number)
        if not warp_info:
            await ctx.message.reply("無效的卡池")
            return
        if not warp_info['expire']:
            pass
        else:
            expire=cmds.time_list_to_datetime(warp_info['expire'])
            if expire<now:
                await ctx.message.reply("該卡池已經過期，待開發者更新")
                return
        pass_type=warp_info['pass_type']
        if pass_type=="regular" and hsr_user['pass']<amount or pass_type=="special" and hsr_user['special_pass']<amount:
            if hsr_user['auto_exchange']:
                amount_to_exchange=amount-hsr_user['pass' if pass_type=='regular' else 'special_pass']
                tmp = await self.exchange(ctx,pass_type,amount_to_exchange)
                if tmp:
                    hsr_user=tmp
                else:
                    return
            else:
                await ctx.message.reply(f"星軌{'通票' if pass_type=='regular' else '專票'}不足，可以透過指令`h!auto_exchange` 開啟自動兌換，或者透過`h!exchange {pass_type} <數量>`兌換星軌{'通票' if pass_type=='regular' else '專票'}")
                return
        
        ##TO DO
        
        if not hsr_user['warp_data'].get(number):
            hsr_user['warp_data'][number]={
                "record":[]
            }
        counter_key=warp_info['counter_key']
        if not hsr_user['counter'].get(counter_key):
            hsr_user['counter'][counter_key]=0
        if not hsr_user['pity_bools'].get(counter_key):
            hsr_user['pity_bools'][counter_key]={
                "is_four_star_pity":False,
                "is_five_star_pity":True
            }
        # is_five_star_pity=hsr_user['pity_bools'][number]['is_five_star_pity']
        # is_four_star_pity=hsr_user['pity_bools'][number]['is_four_star_pity']
        five_star_pity=warp_info['five_star_pity']
        four_star_pity=warp_info['four_star_pity']
        four_star_base_rate=warp_info['four_star_rate']
        five_star_base_rate=warp_info['five_star_rate']
        five_star_max=warp_info['five_star_max']
        counter=hsr_user['counter'][counter_key]
        logger.info(f"read counter:{counter}")
        record=hsr_user['warp_data'][number]['record']
        for i in range(amount):
            critical=False
            counter=counter+1
            logger.info(f'counter:{counter}')
            five_star_rate= max(five_star_base_rate,(counter/five_star_max)**15)
            four_star_rate=four_star_base_rate if counter%10!=0 else 1-five_star_rate
            ps=""
            r=random()
            if r<=four_star_rate:#[*4,3,5]
                quality=4
                if hsr_user['pity_bools'][counter_key]['is_four_star_pity']:
                    tmp=choice(warp_info['up_4']).split('/')
                    hsr_user['pity_bools'][counter_key]['is_four_star_pity']=False
                    ps="[Up!]"
                else:
                    if not warp_info['up_4']:
                        tmp=choice([warp_info['four_star_lightcone'],warp_info['four_star_character']])
                        tmp=choice(tmp).split('/')

                    else:
                        a=[]
                        if warp_info['four_star_lightcone']:
                            a.append(warp_info['four_star_lightcone'])
                        if warp_info['four_star_character']:
                            a.append(warp_info['four_star_character'])
                        tmp=rate_choice(four_star_pity,a,[warp_info['up_4']])
                        tmp=choice(tmp)
                        tmp=choice(tmp)
                        if tmp in warp_info['up_4']:
                            hsr_user['pity_bools'][counter_key]['is_four_star_pity']=False
                            ps="[Up!]"
                        else:
                            hsr_user['pity_bools'][counter_key]['is_four_star_pity']=True
                        tmp=tmp.split('/')
            elif r>1-five_star_rate:#[4,3,*5]
                quality=5
                counter=0
                if hsr_user['pity_bools'][counter_key]['is_five_star_pity']:
                    tmp=choice(warp_info['up_5']).split('/')
                    hsr_user['pity_bools'][counter_key]['is_five_star_pity']=False
                    ps="[UP!]"
                else:
                    if not warp_info['up_5']:
                        tmp=choice([warp_info['five_star_lightcone'],warp_info['five_star_character']])
                        tmp=choice(tmp).split('/')

                    else:
                        critical=True
                        a=[]
                        if warp_info['five_star_lightcone']:
                            a.append(warp_info['five_star_lightcone'])
                        if warp_info['five_star_character']:
                            a.append(warp_info['five_star_character'])
                        tmp:list[list[str]]=rate_choice(five_star_pity,a,[warp_info['up_5']])
                        tmp2=choice(tmp)
                        tmp3=choice(tmp2)
                        tmp=tmp3
                        if tmp in warp_info['up_5']:
                            ps="[Up!]"
                        else:
                            hsr_user['pity_bools'][counter_key]['is_five_star_pity']=True
                            ps="[歪了]"
                        tmp=tmp.split("/")
            else:#[4,*3,5]
                quality=3
                tmp=["lightcone","垃圾","Trash"]
            result=tmp[1:]
            typ=tmp[0]         
            record.append({"time":datetime.datetime.now().strftime('%y/%m/%d %H:%M:%S'),
            "quality":quality,
            "type":typ,
            "result":f'{result[0]} ({result[1]})',
            "ps":ps,
            "critical":critical})

        pulls=record[-amount:]
        qualities=[x['quality'] for x in pulls]
        if 5 in qualities:
            file='pull/5_star.gif'
            wait_time=16
        elif 4 in qualities:
            file='pull/4_star.gif'
            wait_time=14
        else:
            file='pull/3_star.gif'
            wait_time=14
        with open(file, "rb") as f:
            file=discord.File(f,"warp.gif")
        tmp=f"**{warp_info['name']}**\n"
        embed=discord.Embed(title=tmp)
        tmp=""
        embed.set_image(url='attachment://warp.gif')
        m = await ctx.message.reply(embed=embed,file=file)
        await sleep(wait_time)
        embed.set_image(url=None)
        await m.delete()
        m= await ctx.message.reply(embed=embed)
        for i in pulls:
            item = i 
            if item['type']=="lightcone":
                typ="光錐"
            else:
                typ="角色"
            if item['quality'] ==5:
                if item["critical"]:
                    k=tmp
                    k+=f"**🟨\t{'✦✦✦✦✦'}\t{typ}\t????(?????)\t[???]**\n"
                    k+="即將揭曉..."
                    await sleep(0.5)
                    embed.description=k
                    await m.edit(embed=embed)
                    await sleep(0.5)
                    for j in range(3,0,-1):
                        embed.description=k+f" {j} ..."
                        await m.edit(embed=embed)
                        await sleep(1)   
                    tmp+=f"**🟨\t{'✦✦✦✦✦'}\t{typ}\t{item['result']}\t{item['ps']}**"
                else:
                    tmp+=f"**🟨\t{'✦✦✦✦✦'}\t{typ}\t{item['result']}\t{item['ps']}**"
            elif item['quality']==4:
                tmp+=f"🟪\t{'✦✦✦✦ '}{typ:>8}\t{item['result']}\t{item['ps']}"
            else:
                tmp+=f"🟦\t{'✦✦✦     '}{typ:>8}\t{item['result']}"
            tmp+='\n'
            embed.description=tmp
            await m.edit(embed=embed)
            await sleep(0.5)
        hsr_user['counter'][counter_key]=counter
        footer=f"五星綜合保底第 {counter}/{five_star_max} 抽\n"
        if warp_info['pass_type']=="regular":
            hsr_user['pass']-=amount
        else:
            hsr_user['special_pass']-=amount
        footer+=f"剩餘通票: {hsr_user['pass']} | 剩餘專票: {hsr_user['special_pass']} | 剩餘星瓊: {int(hsr_user['jade'])} (每分鐘獲得 1 個)"
        embed.set_footer(text=footer)
        await m.edit(embed=embed)
        ##END
        e=self.write_hsr_data(str(uid),hsr_user)
        if e:
            logger.error(f"Error when saving data:{e}")
            logger.exception(e)
        # await ctx.message.reply(f'amount:{amount},data:\n```\n{hsr_data}```')
        return
    
    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def exchange(self,ctx:commands.Context,typ,amount:int):
        """用星瓊兌換專票或通票，價格皆為1張160星瓊

        Args:
            typ (str): 專票(r)或通票(s)
            amount (int): 兌換張數
        """
        if typ in ("regular","r","R","normal"):
            pass_type="pass"
        elif typ in ("special","s","S"):
            pass_type="special_pass"
        else:
            ctx.message.reply('請輸入正確的參數，用法為: h!exchange regular(r)或special(s) <數量>')
            return
        with open('hsr.json','r',encoding='utf-8') as fd:
            hsr_data=json.load(fd)
        hsr_user:dict=hsr_data[str(ctx.author.id)]
        hsr_user['jade']-=160*amount
        if hsr_user['jade']<0:
            await ctx.message.reply('星瓊不足')
            return
        hsr_user[pass_type]+=amount
        hsr_data[str(ctx.author.id)]=hsr_user
        with open('hsr.json','w',encoding='utf-8') as fd:
            json.dump(hsr_data,fd,indent=4,ensure_ascii=False)
        await ctx.message.reply(f"已成功花費 {amount*160} 個星瓊兌換 {amount} 個星軌{'通票' if pass_type=='pass' else '專票'}，剩餘 {int(hsr_user['jade'])} 個星瓊，剩餘 {hsr_user[pass_type]} 個星軌{'通票' if pass_type=='pass' else '專票'}")
        return hsr_user
        
    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def auto_exchange(self,ctx:commands.Context,arg:str=None):
        """開啟或關閉自動兌換

        Args:
            arg (str): 開啟(true,1)或關閉(false,0)，若未提供參數則為切換(開啟->關閉,關閉->開啟). Defaults to None.
        """
        with open('hsr.json','r',encoding='utf-8') as fd:
            hsr_data=json.load(fd)
        hsr_user:dict=hsr_data[str(ctx.author.id)]
        if arg is None:
            setting=not(hsr_user['auto_exchange'])
        elif arg.lower() in ('true','yes','1'):
            setting=True
        elif arg.lower() in ('false','no','0'):
            setting=False
        else:
            await ctx.message.reply("參數錯誤，應為 true(1)或false(0)")
            return
        hsr_user['auto_exchange']=setting
        hsr_data[str(ctx.author.id)]=hsr_user
        await ctx.message.reply(f"已{'開啟' if setting else '關閉'}自動兌換")
        with open('hsr.json','w',encoding='utf-8') as fd:
            json.dump(hsr_data,fd,indent=4,ensure_ascii=False)
        return
    
    @commands.Cog.listener()
    async def on_command_error(self,ctx, error:Exception):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f'別急哥們，請 {error.retry_after:.2f} 秒後再試一次')
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("你沒有足夠的權限來執行這個指令。")
        elif isinstance(error,commands.CommandNotFound):
            return
        else:
            logger.error(f'未處理的錯誤：{error}')
            logger.exception(error.with_traceback(error.__traceback__))
            raise error   
        

async def setup(bot: commands.Bot):
    await bot.add_cog(HSR_Pull(bot))
        

