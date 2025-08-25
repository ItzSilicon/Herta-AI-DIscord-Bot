
import requests
# from bs4 import BeautifulSoup as bs
import json
import datetime
from google import genai
from google.genai import types
import discord
from discord.abc import Messageable
from IPython.display import Markdown
import textwrap
import logging
import os
from dotenv import load_dotenv 
from random import choice
import re
import asyncio


load_dotenv()


### global vars ###
client=genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
# client = genai.client.AsyncClient(default_client)
bot_id=1396718723464958123
def get_config():
    with open('configuration.json','r',encoding='utf-8') as fd:
        return json.load(fd)

def get_options(arg):
    options={
    "ai_herta_tips": get_config()['tips'],
    "help_commands": get_config()['help_commands'],
    "bot_persona" : get_config()['bot_persona'],
    "style" : get_config()['style'],
    "basic_instruction":get_config()['basic_instruction'],
    "chat_style_disc":[f"{k}: {v}" for k,v in get_config()['style_description'].items()],
    "bot_persona_disc":[f"{k}: {v}" for k,v in get_config()['persona_description'].items()],
    "model_disc":[f"{str(m.name).strip('models/')}" for m in client.models.list() if "generateContent" in m.supported_actions]
    }
    return options[arg]

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO) 
# 3. 建立另一個Handler：將日誌輸出到文件
file_handler = logging.FileHandler('application.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG) # 設定該Handler處理DEBUG級別及以上的訊息
# 4. 建立一個Formatter：定義日誌訊息的格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# 5. 將Formatter設定給Handler
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
# 6. 將Handler添加到Logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)
### ------------ ###

#Provided by AI
class AsyncList:
    def __init__(self, data):
        self.data = data
        self.index = 0

    def __aiter__(self):
        # 返回異步疊代器，在這裡就是物件本身
        return self

    async def __anext__(self):
        # 這是異步生成下一個值的方法
        if self.index < len(self.data):
            # 模擬異步操作，例如從資料庫或網路中獲取資料
            await asyncio.sleep(0.1) 
            value = self.data[self.index]
            self.index += 1
            return value
        else:
            # 迭代結束時拋出 StopAsyncIteration
            raise StopAsyncIteration


def _extract_emoji_ids(message_content):
    # 正則表達式擷取 emoji 名稱和 ID
    pattern = r'<:([a-zA-Z0-9_]+):(\d+)>'
    matches = re.findall(pattern, message_content)
    
    # 建立 {str(id): name} 的 dict
    result = {str(emoji_id): name for name, emoji_id in matches}

    return result


def _add_citations(response):
    # from google api doc
    text = response.text
    supports = response.candidates[0].grounding_metadata.grounding_supports
    chunks = response.candidates[0].grounding_metadata.grounding_chunks

    # Sort supports by end_index in descending order to avoid shifting issues when inserting.
    sorted_supports = sorted(supports, key=lambda s: s.segment.end_index, reverse=True)

    for support in sorted_supports:
        end_index = support.segment.end_index
        if support.grounding_chunk_indices:
            # Create citation string like [1](link1)[2](link2)
            citation_links = []
            for i in support.grounding_chunk_indices:
                if i < len(chunks):
                    uri = chunks[i].web.uri
                    citation_links.append(f"[{i + 1}](<{uri}>)")

            citation_string = ", ".join(citation_links)
            text = text[:end_index] + citation_string + text[end_index:]

    return text

def _load_chat_history(channel:Messageable,guild:discord.Guild,user_info:dict,user:discord.User=None,user_only=False):
    try:
        with open(f"./messages/message_history_{channel.id}.json",'r',encoding='UTF-8') as fd2:
            tmp:dict=json.load(fd2)
        logger.info(f"Chat history loaded for channel {channel.id} in")
        if user_only:
            tmp1= {x:tmp[x] for x in tmp if tmp[x]['author_id'] == str(user.id)}
            tmp2={x:tmp[x] for x in tmp if tmp[x].get('reference')} #剩下有ref的
            tmp3={x:tmp2[x] for x in tmp2 if tmp.get(str(tmp2[x]['reference']))} #去除抓不到的
            tmp4={x:tmp3[x] for x in tmp3 if tmp[str(tmp3[x].get('reference'))].get('author_id')==str(user.id)}
            tmp5={x:tmp4[x] for x in tmp4 if tmp[x]['author_id']==str(bot_id)}
            tmp=tmp1|tmp5
        for i in tmp:
            x=tmp[i]['time']
            timestamp=datetime.datetime(x[0],x[1],x[2],x[3],x[4],x[5],x[6])
            tmp[i]["time"]=timestamp.strftime("%Y年%m月%d日 %H:%M:%S")
        chat_history={}
        chat_history_all=list(tmp.items())
        num_to_take = min(user_info['config']['chat_history_length'], len(chat_history_all))
        for key,  value in chat_history_all[-num_to_take-1:-1]:
            idf= "model" if value['author'] == "黑塔人偶" else "user"
            chat_history[key] = {"author":f'<@{value["author_id"]}>',
                                "content":value['content'],
                                "time":value['time'],
                                "role":idf}
        logger.info(f"Chat history for channel {channel.id} loaded with {len(chat_history)} messages")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # If file doesn"t exist or is corrupted, start with empty dict
        chat_history={}
        logger.error(f"Chat history file for channel {channel.id}  not found or corrupted: {e}")
    
    if not chat_history:
        logger.warning('No History.')
    logger.info(f"Chat history loaded for channel {channel.id}")
    logger.debug(f"Chat history: {json.dumps(chat_history,indent=4,ensure_ascii=False)}")
    return chat_history

def _update_token_balance(user_info:dict,user:discord.User):
    today=datetime.date.today()
    start_day=user_info['start_day']
    # start_day=[6,15,2025]
    start_date=datetime.date(start_day[0],start_day[1],start_day[2])
    diff = today-start_date
    if diff.days>=30 and user_info[str(user.id)]["token_left"]<300:
        logger.info(f"User {user.id} ({user.name}) token reset")
        user_info["token_left"]=300
        user_info["start_day"]=[now_l()[1],now_l()[2],now_l()[0]]
    if user_info["token_left"]<=0:
        logger.info(f"User {user.id} ({user.name}) token left is 0, cannot use AI command")
        reset_date=datetime.datetime.now() + datetime.timedelta(days=30-diff.days)
        return f"代幣不足。 重置於: {30-diff.days} 天後 ({reset_date.year}年{reset_date.month}月{reset_date.day}日)。"




def save_chat(message:discord.Message,bot:discord.ClientUser,specific=None):
    if "## <a:hertakurukuru:1398625201213804614>準備中..." in message.content:
        logger.info(f"AI is thinking, not saving chat" )
        return
    
    server=message.guild if message.guild else message.channel
    channel:Messageable=message.channel
    
    try:
        if message.author.id == bot.id and message.content.split('\n')[-1].startswith('-# '):
            message_to_write="\n".join(message.content.split('\n')[:-1])
        else:
            if specific:
                message_to_write=specific
            else:
                message_to_write=message.content
            
        with open(f'./messages/message_history_{channel.id}.json', 'r',encoding='UTF-8') as f:
            tmp:dict=json.load(f)
        
        logger.info(f"Chat history file loaded for channel {channel.id} in guild {'DM' if type(server) is discord.DMChannel else server.name}")
        
        message_info={
            str(message.id):
                {
                    "server_name": f"{message.author}'s Direct Message" if type(server) is discord.DMChannel else server.name,
                    "channel_id":str(channel.id),
                    "channel_name": "Direct Message" if isinstance(channel, discord.DMChannel) else channel.name,
                    "author":message.author.name,"author_global_name":message.author.global_name,
                    "author_id":str(message.author.id),
                    "time":now_l(),
                    "content":message_to_write,
                    "reference":message.reference.message_id if message.reference else None
                }
            }
        tmp.update(message_info)
        logger.info(f"Chat history for channel {channel.id} in guild {'DM' if type(server) is discord.DMChannel else server.name} updated with message {message.id} from {message.author.name} ({message.author.id})")
        with open(f'./messages/message_history_{channel.id}.json', 'w',encoding='UTF-8') as f:
            json.dump(tmp,f,indent=4,ensure_ascii=False,sort_keys=True)
            logger.info(f'Channel id {channel.id} chat saved')
            del tmp
    except (FileNotFoundError,json.JSONDecodeError) as e:
        logger.warning(f"Error when loading chat: {e}, trying to rebuild chat history for channel {channel.id}")
        message_info={
            str(message.id):
                {
                    "server_name": f"{message.author}'s Direct Message" if type(server) is discord.DMChannel else server.name,
                    "channel_id":str(channel.id),
                    "channel_name": "Direct Message" if isinstance(channel, discord.DMChannel) else channel.name,
                    "author":message.author.name,"author_global_name":message.author.global_name,
                    "author_id":str(message.author.id),
                    "time":now_l(),
                    "content":message_to_write,
                    "reference":message.reference.message_id if message.reference else None
                }
            }
        with open(f'./messages/message_history_{channel.id}.json', 'w', encoding='UTF-8') as f:
            json.dump(message_info,f,indent=4,ensure_ascii=False)
        logger.info(f'channel id {channel.id} is rebuilt')
    except Exception as e:
        logger.error(f"Failed to save chat: {e}")
        logger.exception(e)


def now_l():
    now=datetime.datetime.now()
    return [now.year,now.month,now.day,now.hour,now.minute,now.second,now.microsecond]
def time_list_to_datetime(time_list:list[int]):
    return datetime.datetime(
        year=time_list[0],
        month=time_list[1],
        day=time_list[2],
        hour=time_list[3],
        minute=time_list[4],
        second=time_list[5],
        microsecond=time_list[6]
    )
def toMarkdown(text):
    """
    Convert the text to Markdown format.
    :param text: Text to be converted.
    :return: Markdown object.
    """
    text = text.replace('•', '  *')
    return Markdown(textwrap.indent(text, '> ', predicate=lambda _: True))


def hello(target):
    return f"你好 {target}!"

def mcserver(address):
    response = requests.get(f"https://api.mcsrvstat.us/3/{address}")
    if response.status_code == 200:
        data = response.json()
        if data["online"]:
            if "list" in data["players"]:
                players_list = "\t".join(x["name"].replace("_","\\_") for x in data["players"]["list"])
                players_list+="..."
            else:
                players_list="N/A"
            info=f"""## {address}
            ### **Status**: Online
**IP**: ||{data["ip"]}|| (Don't connect to this IP)
**Port**: {data["port"]}
**Version**: {data["version"]}
**Players**: {data["players"]["online"]}/{data["players"]["max"]}
List:{players_list}
"""
            return info
        else:
            return f"""## {address}
            ### **Status**: Offline/Error
**IP**: ||{data["ip"]}|| (Don"t connect to this IP)
**Pingable**: {data["debug"]["ping"]}
**Error**: {data["debug"]["error"]["ping"]+" "+data["debug"]["error"]["query"]}"""
    else:
        return f"Network Error: {response.status_code}"

def token(userid):
    fd = open('user.json','r')
    data=json.load(fd)
    fd.close()
    if userid not in data:
        return 'N/A (你還沒使用過AI功能)',[0,0,0]
    else:
        return data[userid]['token_left'],data[userid]['start_day']

async def gemini(user:discord.User,message:discord.Message,content,guild:discord.Guild|discord.DMChannel,channel:discord.TextChannel,bot:discord.ClientUser,attachment:list[discord.Attachment]=[]):
    m = await message.reply('## <a:hertakurukuru:1398625201213804614>準備中...\n'+
                            '-# **提示: **\n'+ "-# "+choice(get_options("ai_herta_tips")))
    with open("user.json","r",encoding="utf-8") as fd:
        user_info=json.load(fd)[str(user.id)]
    logger.debug(f"User data for {user.id} ({user.name}) loaded")
    
    ref=None
    ref_msg=None
    reference_author=None
    reference_content=None
    ref=message.reference
    if ref:
        ref_msg= await channel.fetch_message(ref.message_id)
        attachment+=ref_msg.attachments
        reference_author=ref_msg.author
        reference_content=ref_msg.content
    
    model_name=user_info['config']['model']
    if ref_msg:
        emoji_dict=_extract_emoji_ids(message.content)|_extract_emoji_ids(reference_content)
    else:
        emoji_dict=_extract_emoji_ids(message.content)
    images_from_attachment=[]
    images_from_emoji=[]
    image_support_file=('image/png','image/jpg','image/jpeg','image/webp','image/gif')
    
    if attachment:
        await m.edit(content='## <a:hertakurukuru:1398625201213804614>讀取圖片中...\n'+
                                '-# **提示: **\n'+ "-# "+choice(get_options("ai_herta_tips")))
        for x in attachment:
            
            if x.content_type in image_support_file:
                xbyte=requests.get(x.url).content
                ximage=types.Part.from_bytes(
                data=xbyte, mime_type=f"{x.content_type}"   
                )
                images_from_attachment.append(ximage)
            else:
                logger.warning(f"Unsupported file format: {x.content_type} for attachment {x.filename}")
                continue
        
    if user_info['config']['enable_emoji_reading'] and emoji_dict:
        await m.edit(content='## <a:hertakurukuru:1398625201213804614>讀取表情中...\n'+
                                '-# **提示: **\n'+ "-# "+choice(get_options("ai_herta_tips")))
        for y in emoji_dict:
            logger.debug(f"Fetching emoji {y}")
            url=f"https://cdn.discordapp.com/emojis/{y}.gif?v=1"
            filetype='image/gif'
            response=requests.get(url)
            if response.status_code == 415:
                logger.info(f"Emoji {y} is a static image, trying to fetch as PNG")
                url=f"https://cdn.discordapp.com/emojis/{y}.png?v=1"
                response=requests.get(url)
                filetype='image/png'
            if response.status_code != 200:
                logger.warning(f"Failed to fetch emoji {y} from {url}, status code: {response.status_code}")
                continue
            xbyte=response.content
            ximage=types.Part.from_bytes(
                data=xbyte, mime_type=f"{filetype}"
                )
            images_from_emoji.append(ximage)
            
    if user_info['config']['enable_avatar_accessing']:
        await m.edit(content='## <a:hertakurukuru:1398625201213804614>讀取頭像中...\n'+
                                    '-# **提示: **\n'+ "-# "+choice(get_options('ai_herta_tips')))
        xbyte=requests.get(user.avatar).content
        if user.avatar.is_animated():
            filetype='image/gif'
        else:
            filetype='image/png'
        avatar_image=types.Part.from_bytes(
        data=xbyte, mime_type=f"{filetype}"   
                    )
    else:
        avatar_image=None

    chat_history={}
    if user_info['config']['enable_chat_history']:
        chat_history=[]
        if user_info['config']['chat_style']=='default':
            for x in _load_chat_history(channel,guild,user_info,user,True).values():
                chat_history.append({'role':x.get('role'),'parts':[{'text':x.get('content')}]})
        else:
            chat_history={}
            for x in _load_chat_history(channel,guild,user_info).values():
                chat_history[x.get('author')]="{}\n--{}".format(x.get('content'),x.get('time'))
    else:
        logger.info(f"User {user.id} ({user.name}) has disabled chat history.")
    
    logger.debug(f'chat_history: {chat_history}')
    
    tmp=_update_token_balance(user_info,user)
    if _update_token_balance(user_info,user):
        return tmp
    del tmp
    basicinfo=""
    try:
        basicinfo=f"""基本資訊：
日期：{now_l()[0]}-{now_l()[1]}-{now_l()[2]} {datetime.datetime.now().strftime('%A')}
時間：{now_l()[3]}:{now_l()[4]}:{now_l()[5]} (UTC+8 台灣時間)
機器人(你)的使用者id: <@{bot_id}> 
使用者(開拓者)的帳號：{user.name}
使用者(開拓者)的id: <@{user.id}> (提及開拓者時請使用此ID)
開拓者的名稱：{user.global_name if user.global_name else user.name}
開拓者的顯示名稱：{user.display_name}
伺服器名稱：{"N/A" if type(guild) is discord.DMChannel else guild.name}
伺服器成員數量：{guild.member_count if not type(guild) is discord.DMChannel else 'N/A'}
頻道名稱：{"私訊" if type(channel) is discord.DMChannel else channel.name}
頻道類型：{channel.type}
剩餘代幣：{user_info["token_left"]:.2f}
{'此次請求有包含附件圖片' if images_from_attachment else '此次請求沒有包含附件圖片'}
{'此次請求有包含外部表情，請試著透過表情理解用戶想要表達的含意' if images_from_emoji else '此次請求沒有包含外部表情'}
轉圈圈表情：<a:hertakurukuru:1398625201213804614>
模型:{model_name}
{f'開拓者提及訊息內容：{reference_author}發送訊息: {reference_content}' if user_info['config']['chat_style']!='default' else ""}
{"歷史聊天訊息："if user_info['config']['chat_style']!='default' else ""}
{chat_history if (chat_history and user_info['config']['chat_style']!='default') else "無歷史聊天訊息或歷史聊天訊息已關閉"}

要求：
1. 以Markdown格式生成
2. 風格: {get_options("style")[user_info['config']['chat_style']]}
"""
    except KeyError as e:
        await m.edit(content=f"抱歉，由於設定的鍵值對可能因變動而無法對照，煩請輸入指令 !cfg chat_style default 重設設定。")
        return
        
    
    except Exception as e:
        await m.edit(content=f"錯誤: {e}")
        return

    try:
        tools=[] #for future extension
        logger.info(f"User {user.id} ({user.name}) requested Gemini with content: {content}")
        await m.edit(content='## <a:hertakurukuru:1398625201213804614>思考中...\n'+
                                '-# **提示: **\n'+ "-# "+choice(get_options('ai_herta_tips')))
        persona_text = get_options("bot_persona")[user_info['config']['bot_persona']]    
        combined_system_instruction = f"{persona_text}" 
        if user_info['config']['enable_search']:
            grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
            )
            tools.append(grounding_tool)
        
        contents=[]
        if emoji_dict:
            for i,(k,v) in enumerate(emoji_dict.items()):
                contents.append(f'emoji #{k}:{v}')
                contents.append(images_from_emoji[i])
        if user_info['config']['chat_style']!='default':
            contents+=[content,basicinfo]
        else:
            contents+=[content]
        
        if avatar_image:
            contents+=["這是該開拓者的頭像，如果沒有特意提及不用理解這個頭像"]+[avatar_image]
        if images_from_attachment:
            for i in range(len(images_from_attachment)):
                contents.append(f'圖片{i+1}')
                contents.append(images_from_attachment[i])
        logger.info("Generateing...")
        tmp=''
        cost=0
        chunk=None
        if user_info['config']['chat_style']=='default':
            chat=client.aio.chats.create(
                model=model_name,
                config={
                "temperature": 1,
                "system_instruction": get_options("basic_instruction")+persona_text+basicinfo,
                "tools":tools
                },history=chat_history
            )
            response=await chat.send_message_stream(
                message=contents
            )
        else:
            response = await client.aio.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config={
                    "temperature": 1,
                    "system_instruction": get_options("basic_instruction")+persona_text,
                    "tools":tools
                    }
                )
        result=""
        try:
            async for chunk in response:
                if chunk.text:
                    tmp+="".join(chunk.text)
                else:
                    continue
                if len(tmp)>=2000:
                    result+=tmp
                    logger.info(f"Message content exceeds 2000 characters, splitting message")
                    t2=[]
                    t=tmp.split('\n\n')
                    l=len(tmp)
                    while l>=2000:
                        l-=len(t[-1])+2
                        t2.append(t.pop())
                    tmp="\n\n".join(t2)
                    m= await m.channel.send(tmp)
                    logger.info(f"New message sent for user {user.id} ({user.name}) due to character limit")

                m = await m.edit(content=tmp)
            if not chunk or not tmp:
                logger.warning(f"Gemini response for user {user.id} ({user.name}) is empty")
                return "Gemini 回傳了空氣給你，笑死。"
            
            cost=chunk.usage_metadata.total_token_count
            result+=tmp
            if chunk.candidates[0].grounding_metadata:
                cost*=3
            
            logger.info(f"Gemini response generated for user {user.id} ({user.name}) with cost: {cost} tokens")
            
        except Exception as e:
            logger.error(f"Error during Gemini response generation for user {user.id} ({user.name}): {e}")
            message.channel.send(f"Interal Error: {e}")
            raise e
        
        logger.info("Completed!")
        logger.info('calculate cost...')
        user_info["token_left"]-=cost/1000
        logger.info('final edit.../Save response')
        save_chat(m,m.author,result)
        await m.edit(content=tmp+f"\n-# 本次請求花費 {cost/1000} 個代幣(Token)，剩餘 {user_info['token_left']:.2f} 個代幣\n-# **{user_info['config']['chat_style']}** style | **{user_info['config']['bot_persona']}** persona")
                                                
    except Exception as e:
        logger.error(f"Error generating Gemini response for user {user.id} ({user.name}): {e}")
        logger.exception(e)
        await message.channel.send(content=f"<@1110595121591898132> 請你來修Bug: \n```{e.with_traceback(e.__traceback__)}```")
        raise e
    with open("user.json","r",encoding='utf-8') as fd:
        user_list:dict=json.load(fd)
    logger.info(f"loaded user data for {user.id} ({user.name})")
    user_list[str(user.id)]['token_left']=user_info['token_left']
    user_list[str(user.id)]['last_request']=now_l()
    logger.info(f"Updated token balance for user {user.id} ({user.name}) to {user_info['token_left']:.2f}")
    with open("user.json","w", encoding="utf-8") as fd:
        fd.write("")
        json.dump(user_list, fd, ensure_ascii=False,indent=4)
    logger.info(f"User {user.id} ({user.name}) data saved")
    return 1

def set_token(user: discord.User,target_user:discord.User,amount:float):
    if user.id == 1110595121591898132:
        with open("user.json","r",encoding="utf-8") as fd:
            user_list=json.load(fd)
        user_list[str(target_user.id)]["token_left"]=amount
        with open("user.json","w", encoding="utf-8") as fd:
            fd.write("")
            json.dump(user_list, fd, ensure_ascii=False,indent=4)
        return f"已成功設定使用者<@{target_user.id}> ({target_user.global_name})代幣數量為 {amount} 。"
    else:
        return "權限請求失敗，請聯絡黑塔本人(Discord: lxtw)"