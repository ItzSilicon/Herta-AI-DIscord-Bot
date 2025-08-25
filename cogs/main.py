import datetime
import discord 
import json
from discord.ext import commands
from discord import File
import logging
import cmds
from cmds import AsyncList
import os
from discord import NotFound
from random import randint
import psutil
bot_id=1396718723464958123
dev=1110595121591898132


# Set up logging
logger = logging.getLogger(__name__)

def _recursive_access_data(data,args):
    if not data:
        return None
    next_level=args.pop(0)
    try:
        data=data[next_level]
    except KeyError:
        data=data.get(next_level)
    except IndexError:
        return None
    if args:
        return _recursive_access_data(data,args)
    else:
        return data
    
def open_json(filename_no_dot_json,*args):
    with open(f'{filename_no_dot_json}.json','r',encoding='utf-8') as fd:
        data = json.load(fd)
    return _recursive_access_data(data,args)

class Main(commands.Cog):
    
    def __init__(self,bot:commands.Bot):
        self.bot=bot


    def update_user_data(self,message:discord.Message):
        with open('user.json','r',encoding='UTF-8') as fd:
            user_data:dict=json.load(fd)
        logger.debug(f"User data loaded: {len(user_data)} users found")
        user_to_write={"user":str(message.author.name),
                        "global_name":message.author.global_name,
                        }
        if str(message.author.id) not in user_data:
            logger.info(f"New user detected: {message.author.id} ({message.author.name})")
            user_to_write={"user":str(message.author.name),
                        "global_name":message.author.global_name,
                        "last_request":[2000,1,1,0,0,0,0],
                        "config":{
                                "model":"gemini-2.5-flash",
                                "enable_chat_history":True,
                                "chat_history_length":10,
                                "chat_style":"default",
                                "enable_search":True,
                                "bot_persona":"default",
                                "enable_emoji_reading":True,
                                "enable_avatar_accessing":False
                        },
                        "token_left":float(300.0),
                        "start_day":cmds.now_l()[:3]
                        }
            try:
                user_data[str(message.author.id)]=user_to_write
            except Exception as e:
                logger.error(f"Error writing new user data for {message.author.id}: {e}")
                return
        else:
            #check user data is valid
            user=user_data[str(message.author.id)]
            for k,v in {
                        "last_request":[2000,1,1,0,0,0,0],
                        "config": {
                            "model":"gemini-2.5-flash",
                            "enable_chat_history":True,
                            "chat_history_length":10,
                            "chat_style":"default",
                            "enable_search":True,
                            "bot_persona":"default",
                            "enable_emoji_reading":True,
                            "enable_avatar_accessing":False
                        },
                        "token_left":float(),
                        "start_day":[0]*3}.items():
                
                if k == "config":
                    user_to_write[k]={}
                    for ck, cv in v.items():
                        if ck in user[k]:
                            if type(user[k].get(ck)) is type(cv):
                                user_to_write[k][ck]=user[k][ck]
                            else:
                                logger.warning(f"User data for {message.author.id} ({message.author.name}) key {k}.{ck} is invalid, resetting to default")
                                user_to_write[k][ck]=cv
                        else:
                            logger.warning(f"User data for {message.author.id} ({message.author.name}) key {k}.{ck} is missing, resetting to default")
                            user_to_write[k][ck]=cv
                if user.get(k) and type(user[k]) is type(v):
                    continue
                else:
                    logger.warning(f"User data for {message.author.id} ({message.author.name}) key {k} is invalid, resetting to default")
                    user_to_write[k]=v
                    
                
        logger.debug(f"User data for {message.author.id} ({message.author.name}) loaded")
        for k,v in user_to_write.items():
            user_data[str(message.author.id)][k]=v
        with open('user.json','w',encoding="UTF-8") as fd2:
            json.dump(user_data,fd2,indent=4,ensure_ascii=False)
        logger.info(f"user id {message.author.id} ({message.author.name}) data saved")
        return user_data

    def update_guild_data(self,guild:discord.Guild):
        with open ('guild.json','r',encoding='utf-8') as fd:
            guilds_data=json.load(fd)
            guild_data=guilds_data.get(str(guild.id))
        update_list={
                "name":guild.name,
                "channels":[{str(x.id):x.name} for x in guild.channels],
                "members":[{str(x.id):x.global_name} for x in guild.members]}
        if guild_data:
            for k,v in update_list.items():
                guild_data[k]=v
            guilds_data[str(guild.id)]=guild_data
        else:
            guilds_data[str(guild.id)]={
                "name":guild.name,
                "channels":[{str(x.id):x.name} for x in guild.channels],
                "members":[{str(x.id):x.global_name} for x in guild.members],
                "config":{
                    "ban_from_using_ai":[],
                    "allowed_channel":[]}
            }
        with open('guild.json','w',encoding='utf-8') as fd:
            json.dump(guilds_data,fd,indent=4,ensure_ascii=False)
        return guild_data
    
    @commands.Cog.listener()
    async def on_message(self,message:discord.Message):
        
        user_data=self.update_user_data(message)
        guild_data=self.update_guild_data(message.guild) if message.guild else None
        
        server=message.guild if message.guild else message.channel
        channel=message.channel
        
        # load chat history
        logger.info('Start to save chat')
        try:
            cmds.save_chat(message,self.bot.user)
        except Exception as e:
            logger.error(f"Error saving chat for {message.author.id} ({message.author.name}): {e}")
                
        #command
        
        if message.author.id == bot_id:
            logger.info(f"Bot {self.bot.user.name} received a message from itself, ignoring.")
            return
        if message.author.bot:
            logger.info(f"Ignoring message from bot: {message.author.name} ({message.author.id})")
            return
        

        if self.bot.user.mentioned_in(message) or message.content.startswith('h!gemini'):
            if guild_data:
                if str(message.author.id) in guild_data['config']['ban_from_using_ai']:
                    logger.info(f"User {message.author.id} ({message.author.name}) is banned from using AI features")
                    dm= await message.author.create_dm()
                    await dm.send(f"{message.author.mention}，你被ban了，無法在 **{message.guild.name}** 使用該機器人的功能")
                    return
            if message.content.startswith('h!rinfo'):
                await message.channel.send(f"{message.author.mention}，黑塔的內部資訊不值得你這麼關心，管好你自己",file=File('do_your_business.jpg'))
                return
            if message.content.startswith('h!') and not message.content.startswith('h!gemini'):
                await message.channel.send(f"{message.author.mention}，不要同時使用指令又同時提及我，就好像量子糾纏一樣，一下要我執行指令，一下又要我回答問題，我要同時給你兩個型態的答案嗎？")
                return
            logger.info(f"User {message.author.id} ({message.author.name}) mentioned the bot or used h!gemini command")
            last_request_time=cmds.time_list_to_datetime(user_data[str(message.author.id)]['last_request'])
            current_time=cmds.time_list_to_datetime(cmds.now_l())
            diff=current_time - last_request_time
            if diff.seconds < 8:
                await message.channel.send(f"慢點，{message.author.mention}，請你 {8-diff.seconds} 秒後再試一次。")
                return
            await channel.typing()
            # print(image)
            if message.content.startswith("h!gemini"):
                content=" ".join(message.content.split()[1:])
            else:
                content=message.content
            reply= await cmds.gemini(
                message.author,
                message,
                content,
                server,
                channel,
                self.bot.user,
                message.attachments,
                )
            logger.info(f"Reply generated for user {message.author.id} ({message.author.name})")
            if reply == 1:
                logger.info(f"Successfully replied to user {message.author.id} ({message.author.name})")
                return
            else:
                logger.error(f"Failed to generate reply for user {message.author.id} ({message.author.name}): {reply}")
                await message.reply(reply)
                return
            
        if 'nigger' in message.content:
            if guild_data:
                if str(message.author.id) in guild_data['config']['ban_from_using_ai']:
                    return
            r=randint(0,100)
            if r>98:
                await message.reply("https://www.youtube.com/watch?v=YG4iTGjuoKw")
                return
            else:
                await message.reply(file=File(f'nig/nig{r%14}.gif'))
                return
        
        if 'kuru' in message.content:
            if guild_data:
                if str(message.author.id) in guild_data['config']['ban_from_using_ai']:
                    return
            await message.reply(content='<a:hertakurukuru:1398625201213804614>')
            return 

        if guild_data and message.content.startswith("h!"):
            if str(message.author.id) in guild_data['config']['ban_from_using_ai']:
                logger.info(f"User {message.author.id} ({message.author.name}) is banned from using AI features")
                dm= await message.author.create_dm()
                await dm.send(f"{message.author.mention}，你被ban了，無法在 **{message.guild.name}** 使用該機器人的功能")
                return          


    #User Commands(Level 3)

    @commands.command(aliases=['hi','halo'])
    async def hello(self,ctx:commands.Context):
        """向開拓者問好
        """
        await ctx.message.reply(cmds.hello(ctx.author))

    @commands.command(aliases=['mcs'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def mcserver(self,ctx:commands.Context,ip:str=None):
        """透過IP查詢Minecraft伺服器資訊
        用法:``h!mcserver <IP>``

        Args:
            ip (str): IP，必要參數
        """
        if not ip:
            await ctx.message.reply(f"開拓者，沒給IP是要讓我猜嗎")  
            return
        
        await ctx.message.reply(cmds.mcserver(ip))
        await ctx.send(f'https://api.loohpjames.com/serverbanner.png?ip={ip}')

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def info(self,ctx:commands.Context,uid:int=0):
        """透過使用者ID查詢該開拓者的內部資料及設定
        用法: ``h!info <ID>``
        Args:
            uid (int): 使用者ID，透過Discord開發者功能即可取得，必要參數
        """
        with open('user.json','r',encoding='UTF-8') as fd:
            users_data:dict=json.load(fd)
        if not uid:
            uid=ctx.author.id
        try:
            user_data:dict[str,dict]=users_data[str(uid)]
            user_data['last_request']=cmds.time_list_to_datetime(user_data['last_request']).strftime('%Y年%m月%d日 %H:%M:%S')
            tmp=user_data['start_day']
            user_data['start_day']=datetime.datetime(tmp[0],tmp[1],tmp[2]).strftime('%Y年%m月%d日')
            reply="```\n"
            tmp=json.dumps(user_data,indent=4,ensure_ascii=False,separators=['',': '])
            tmp=tmp.replace('"','').replace('{','').replace('}','')
            reply+=tmp
        except KeyError:
            reply+="使用者不存在"
            reply+="\n```"
            await ctx.message.reply(reply)
            return
        reply+="\n```"
        await ctx.message.reply(reply)

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def rinfo(self,ctx:commands.Context):
        """透過引用訊息的方式查詢該開拓者的資料與設定
        用法:``!rinfo``，必須引用一則訊息
        Args:
            (透過引用訊息觸發)
        """
        ref=ctx.message.reference
        if ref is None:
            await ctx.message.reply("請引用一條消息來查看使用者資訊")
            return
        ref_id=ref.message_id
        try:
            ref_message=await ctx.channel.fetch_message(ref_id)
        except Exception as e:
            await ctx.message.reply(f"沒有引用的訊息、訊息不存在或已被刪除:\n```\n{e}```")
            return
        if ref_message.author.id == bot_id:
            await ctx.message.reply("這是我發的消息，請使用 h!info <user_id> 來查看使用者資訊")
            return
        author_id=ref_message.author.id
        return await self.info(ctx, author_id)

    @commands.command()
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def token(self,ctx:commands.Context,uid:int=0):
        """查詢開拓者的剩餘代幣及重設日期
        用法:``h!token <ID>``
        Args:
            uid (int):若無指定參數則為查詢自己的代幣資訊，若有，則查詢指定開拓者代幣資訊
        """
        if not uid:
            uid=ctx.author.id
        try:
            data=cmds.token(str(uid))
            await ctx.message.reply(f"""剩餘代幣: {data[0]}
    上次重置日期: {data[1][0]}/{data[1][1]}/{data[1][2]}""")
        except Exception as e:
            ctx.message.reply(f"錯誤： {e}")
            raise e

    @commands.command(aliases=['cfg'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def config(self,ctx:commands.Context, key=None, value=None):
        """設定個人化資料
        用法:h!config <key> <value>
        Args:
            key (str): 參數名稱，如果未指定參數，則顯示完整個人化設定，
            value (Any): 參數值，如果未指定參數則顯示該參數的值
        """
        fd =open('user.json', 'r', encoding='UTF-8')
        user_data=json.load(fd)
        fd.close()
        user_config = user_data[str(ctx.author.id)]['config']
        if not key:
            tmp=json.dumps(user_config,indent=4,ensure_ascii=False)
            await ctx.message.reply(f"選項: ```\n{tmp}```\n, 使用 h!config <選項> <值> 來設定選項")
            return
        options=[]
        if key in user_config:
            if type(user_config[key]) is bool:
                options=["True","False","1","0","yes","no"]
            elif type(user_config[key]) in (float,int):
                options=["數值(限制取決於該值設定)"]
            elif type(user_config[key]) is str:
                options=cmds.get_options(f"{key}_disc")
            else:
                options=["未指定格式"]
            tmp="\n".join(options)
        else:
            await ctx.message.reply(f"未知選項: `{key}`")
            return
        if not value:
            await ctx.message.reply(f"```\n{key}: {user_config[key]}```\n選項:\n```\n{tmp}```")
            return


        if key == "chat_history_length":
            try:
                value = int(value)
                if value < 1 or value > 20:
                    await ctx.message.reply(f"錯誤: 請輸入1到20之間的數字")
                    return
            except ValueError as e:
                await ctx.message.reply(f"錯誤: `{e}`，請輸入一個有效的數字")
                return
            
        if key == "model":
            if value not in cmds.get_options("model_disc"):
                await ctx.message.reply('警告: 請確認您輸入的模型是否存在，且部分模型可能不支援圖形輸入，詳情請參考Gemini官方文檔。已知可用模型：'+'\n'+"```"+"\n".join(options)+"```")
                
        
        if key in ("enable_chat_history","enable_search","enable_avatar_accessing","enable_emoji_reading",):
            if value.lower() in ["true", "yes", "1"]:
                value = True
            elif value.lower() in ["false", "no", "0"]:
                value = False
            else:
                await ctx.message.reply("錯誤: 請輸入 `true/false` 或 `yes/no`")
                return
            
        if key in ("chat_style","style"):
            styles=cmds.get_options("chat_style")
            if value not in styles:
                
                await ctx.message.reply(f"錯誤：目前僅提供{len(styles)}個風格:\n"+"\n".join(list(styles.keys())))
                return
            
        if key in ("bot_persona","persona"):
            personas=cmds.get_options("bot_persona")
            if value not in personas:
                await ctx.message.reply(f"錯誤：目前僅提供{len(personas)}個人設:\n"+"\n".join(list(personas.keys())))
                return
        user_config[key] = value
        user_data[str(ctx.author.id)]['config'] = user_config
        with open('user.json', 'w', encoding='UTF-8') as fd:
            json.dump(user_data, fd, indent=4, ensure_ascii=False)
        await ctx.message.reply(f"已設定 `{key}` 為 `{value}`")


    @commands.command(aliases=['ins'])
    @commands.cooldown(1,300, commands.BucketType.user)
    async def instruction(self,ctx:commands.Context):
        """傳送操作說明至開拓者私訊
        """
        with open('instruction.markdown', 'r', encoding='utf-8') as fd:
            instruction = fd.read()
        
        dm=None
        try:
            dm= await ctx.author.create_dm()
        except discord.Forbidden:
            await ctx.message.reply("無法發送私訊，請檢查您的隱私設定。")
            return
        except discord.HTTPException as e:
            await ctx.message.reply(f"發送私訊時發生錯誤：{e}")
            return
        if not dm:
            await ctx.message.reply("無法創建私訊頻道，請檢查您的隱私設定。")
            return
        await dm.send(f"""wait...""")
        tmp=AsyncList(instruction.split('\n##'))
        async for i in tmp:
            await sleep(2)
            await dm.send("\n##"+i)
        if ctx.author.guild_permissions.administrator:
            with open('instruction_admin.markdown', 'r', encoding='utf-8') as fd:
                instruction_admin = fd.read()
            await dm.send("wait...")
            async for i in AsyncList(instruction_admin.split('\n##')):
                await sleep(2)
                await dm.send("\n##"+i)
        await ctx.message.reply("所有指令說明已發送到您的私訊。請檢查您的私訊。")

    @commands.command(aliases=['nigge','nigg','nig','ni'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def nigger(self,ctx:commands.Context):
        """隨機傳送黑人圖片
        """
        r=randint(0,100)
        if r>98:
            await ctx.message.reply(file=File('nig/nig15.mp4'))
            return
        else:
            await ctx.message.reply(file=File(f'nig/nig{r%14}.gif'))
            return


    @commands.command(aliases=['kuru','spin'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def kurukuru(self,ctx:commands.Context):
        """轉圈圈!
        """
        await ctx.message.reply(content='<a:hertakurukuru:1398625201213804614>')
        
    @commands.command(aliases=['cpu','ram'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def hstat(self,ctx:commands.Context):
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_name = line.strip().split(": ")[1]
                        break
        except Exception as e:
            await ctx.message.reply(f"無法取得硬體資訊:{e}")
        cpu_usage=int(psutil.cpu_percent(interval=1))
        ram=psutil.virtual_memory()
        ram_used=round(ram.used/1024**3,2)
        ram_total=round(ram.total/1024**3,2)
        ram_percent=int(ram.percent)
        info=f"""
## **CPU**
**{cpu_name}**
**{psutil.cpu_count(logical=False)}** 核心 / **{psutil.cpu_count(logical=True)}** 執行緒
頻率: **{psutil.cpu_freq().current/1000 if psutil.cpu_freq() else 'N/A':.2f} GHz**
| {'█'*(cpu_usage//4)+'▒'*(25-cpu_usage//4)} | {cpu_usage}%
## **RAM**
**{ram_used} GB** / {ram_total} GB 
| {'█'*(ram_percent//4)+'▒'*(25-ram_percent//4)} | {ram_percent}%
"""
        await ctx.message.reply(info)

    #Admin Commands(Level 2)

    @commands.command(aliases=['b','bn'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ban(self,ctx:commands.Context,user_id, ban=True):
        """允許、禁止開拓者使用機器人(限伺服器管理員使用)
        用法:!ai_ban <uid> [ban/unban(bool)]
        Args:
            user_id (int): 使用者id
            ban (bool): 若未給定參數，則禁止該開拓者，等同於True，若為False，則允許該開拓者
        """
        if type(ctx.channel) is discord.DMChannel:
            await ctx.message.reply("這個指令只能在伺服器中使用")
            return
        try:
            user= await ctx.guild.fetch_member(int(user_id))
        except NotFound:
            await ctx.message.reply(f"錯誤：找不到ID為 {user_id} 的使用者")
            return
        if not user:
            logger.warning(f"User with ID {user_id} not found in guild {ctx.guild.name}")
            user_name= f'<@{user_id}>'
        else:
            user_name = user.global_name + f'(<@{user_id}>)'
        if not (ctx.author.guild_permissions.administrator or ctx.author.id == dev):
            await ctx.message.reply("你不是該伺服器的管理員。")
            return  
        with open('guild.json', 'r', encoding='utf-8') as fd:
            guilds_data= json.load(fd)
        guild_data = guilds_data.get(str(ctx.guild.id))
        if not guild_data:
            await ctx.message.reply("錯誤：無法找到伺服器資料")
            return
        else:
            if ban:
                if str(user_id) in guild_data['config']['ban_from_using_ai']:
                    await ctx.message.reply(f"使用者 {user_name} 已經被禁止使用AI功能")
                    return
                guild_data['config']['ban_from_using_ai'].append(str(user_id))
                guilds_data[str(ctx.guild.id)] = guild_data
            else:
                if str(user_id) not in guild_data['config']['ban_from_using_ai']:
                    await ctx.message.reply(f"使用者 {user_name} 尚未被禁止使用AI功能")
                    return
                guild_data['config']['ban_from_using_ai'].remove(str(user_id))
                guilds_data[str(ctx.guild.id)] = guild_data
        with open('guild.json', 'w', encoding='utf-8') as fd:
            json.dump(guilds_data, fd, indent=4, ensure_ascii=False)
        await ctx.message.reply(f"已將使用者 {user_name} 設為 {'禁止' if ban else '允許'}使用AI功能")


    @commands.command(aliases=['st'])
    async def setToken(self,ctx:commands.Context,uid,token):
        """設定使用者Token數(僅限開發者使用)
        用法:h!setToken <ID> <Amount>
        Args:
            uid (int): 使用者ID
            token (float): 數值
        """
        try:
            target_user= await self.bot.fetch_user(int(uid))
        except discord.NotFound:
            await ctx.message.reply(f"錯誤：找不到ID為 {uid} 的使用者")
            return
        await ctx.send(ctx.message.author.mention+cmds.set_token(ctx.author,target_user,float(token)))



async def setup(bot: commands.Bot):
    await bot.add_cog(Main(bot))
