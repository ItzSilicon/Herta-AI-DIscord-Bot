from encodings import aliases
import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv 
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO) 
# 3. 建立另一個Handler：將日誌輸出到文件
file_handler = logging.FileHandler('application.log', encoding='utf-8')
file_handler.setLevel(logging.INFO) # 設定該Handler處理DEBUG級別及以上的訊息
# 4. 建立一個Formatter：定義日誌訊息的格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# 5. 將Formatter設定給Handler
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
# 6. 將Handler添加到Logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)


load_dotenv()
intents = discord.Intents.all()
intents.message_content = True
bot_id=1396718723464958123
dev=1110595121591898132
bot = commands.Bot(command_prefix = "h!", intents = intents)



# 當機器人完成啟動時
@bot.event
async def on_ready():
    with open('tmp.txt','r') as fd:
        channel_id=fd.read()
    if not channel_id:
        return
    channel=bot.get_channel(int(channel_id))
    if not channel:
        return
    await channel.send(f"重啟成功，{bot.user.name} 已經上線！")


# 載入指令程式檔案
@bot.command(aliases=['ld'])
async def load(ctx:commands.Context, extension="main"):
    if ctx.message.author.id == dev:
        await bot.load_extension(f"cogs.{extension}")
        await ctx.send(f"Loaded {extension} done.")
    else:
        await ctx.message.reply("你不是開發者，不能使用該指令")
        

# 卸載指令檔案
@bot.command(aliases=['ul'])
async def unload(ctx:commands.Context, extension="main"):
    if ctx.message.author.id == dev:
        await bot.unload_extension(f"cogs.{extension}")
        await ctx.send(f"UnLoaded {extension} done.")
    else:
        await ctx.message.reply("你不是開發者，不能使用該指令")

# 重新載入程式檔案
@bot.command(aliases=['rl'])
async def reload(ctx:commands.Context, extension="main"):
    if ctx.message.author.id == dev:
        await bot.reload_extension(f"cogs.{extension}")
        await ctx.send(f"ReLoaded {extension} done.")
    else:
        await ctx.message.reply("你不是開發者，不能使用該指令")
        
        
@bot.command(aliases=['rs'])
async def restart(ctx:commands.Context):
    """重啟機器人(限開發者使用)
    """
    if ctx.author.id==dev:
        with open('tmp.txt','w') as fd:
            fd.write(str(ctx.message.channel.id))
        await ctx.message.reply("機器人正在重啟中...")
        exit(0)
    else:
        await ctx.message.reply("你無法重啟我，但是我可以為你轉圈圈\n# <:hertakurukuru:1398625201213804614>")

# 一開始bot開機需載入全部程式檔案
async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

async def main():
    async with bot:
        await load_extensions()
        await bot.start(token=os.getenv("DISCORD_TOKEN"))
        
@bot.event
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

# 確定執行此py檔才會執行
if __name__ == "__main__":
    asyncio.run(main())
