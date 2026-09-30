import discord
TOKEN = "invalid_token_test"
client = discord.Client(intents=discord.Intents.default())
@client.event
async def on_ready():
    print(f"已登录：{client.user}")
client.run(TOKEN)
