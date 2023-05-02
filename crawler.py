import httpx
import asyncio
import os
import yaml
import random
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, CHAR, TEXT
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert

if not os.path.exists("config.yaml"):
    with open("config.yaml", "w", encoding="UTF-8") as f:
        f.write("""# Path: config.yaml
# 数据库配置
dbhost: 
dbport: 
dbuser: 
dbpassword: 
dbname: 
# API配置
apihost: 
apiport: 
""")
    raise Exception("请先配置config.yaml文件！")

with open("config.yaml", "r", encoding="UTF-8") as f:
    conf = yaml.load(f, Loader=yaml.FullLoader)

region_list = ["en-us", "zh-cn", "ja-jp", "de-de", "en-gb", "es-es",
           "pt-br", "en-au", "en-ca", "fr-fr", "en-in", "it-it"]

sql_engine = create_engine(f'mysql+pymysql://{conf["dbuser"]}:{conf["dbpassword"]}@{conf["dbhost"]}:{conf["dbport"]}/{conf["dbname"]}')
sql_metadata = MetaData(sql_engine)
sql_tables = {}
for region in region_list:
    sql_tables[region] = Table(region, sql_metadata,
        Column("hsh", CHAR(32), primary_key=True),
        Column("date", Integer),
        Column("url", String(200)),
        Column("urlbase", String(200)),
        Column("title", String(100)),
        Column("desc", TEXT),
        Column("copyright", TEXT)
    )
sql_metadata.create_all()

def sql_replace(sess: Session, table, **kwargs):
    insert_stmt = insert(table).values(kwargs)
    on_duplicate_key_stmt = insert_stmt.on_duplicate_key_update(**kwargs)
    sess.execute(on_duplicate_key_stmt)

async def get(url: str, *args, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        return await client.get(url, timeout=60, *args, **kwargs)

async def get_region_info(region: str):
    jsonurl = f"https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt={region}"
    img_info = (await get(jsonurl)).json()["images"][0]
    return img_info


async def process_region(region: str):
    info = await get_region_info(region)
    # await cache_img(img_info, region)
    with Session(sql_engine) as sess:
        sql_replace(sess, sql_tables[region],
                    hsh = info["hsh"],
                    date = int(info["enddate"]),
                    url = f"https://www.bing.com{info['url']}",
                    urlbase = info["urlbase"],
                    title = info["title"],
                    desc = "",
                    # desc = info["desc"],
                    copyright = info["copyright"]
        )
        sess.commit()

async def main():
    with Session(sql_engine) as sess:
        for date in range(20230000, 20231000):
            sql_replace(sess, sql_tables["zh-cn"],
                        hsh = hex(random.randint(0, 2**32))[2:],
                        date = date
            )
        sess.commit()

if __name__ == "__main__":
    asyncio.run(main())