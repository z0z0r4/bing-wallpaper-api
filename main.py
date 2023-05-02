from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.staticfiles import StaticFiles
import uvicorn

import traceback
from datetime import datetime
from functools import wraps
import yaml
import os

from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, CHAR
from sqlalchemy.orm import Session


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
api = FastAPI()

sql_engine = create_engine(f'mysql+pymysql://{conf["dbuser"]}:{conf["dbpassword"]}@{conf["dbhost"]}:{conf["dbport"]}/{conf["dbname"]}')
sql_metadata = MetaData(sql_engine)
sql_tables = {}
for region in region_list:
    sql_tables[region] = Table(region, sql_metadata,
        Column("hsh", CHAR(32), primary_key=True),
        Column("date", Integer),
        Column("url", String(100)),
        Column("urlbase", String(100)),
        Column("title", String(100)),
        Column("desc", String(1000)),
        Column("copyright", String(100))
    )

def add_ststus(func):
    @wraps(func)
    async def status(*args, **kwargs):
        try:
            res = await func(*args, **kwargs)
        except Exception as e:
            traceback.print_exception(e)
            return JSONResponse(status_code=500, content={"status": "failed", "error": str(e)})
        else:
            return JSONResponse(status_code=200, content={"status": "success", "data": res})
    return status

# Docs
api.mount("/static", StaticFiles(directory="static"), name="static")
@api.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=api.openapi_url,
        title=api.title + " - Swagger UI",
        oauth2_redirect_url=api.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )

@api.get("/", description="返回API信息")
@add_ststus
async def root():
    return {"message": "Bing Wallpapers API", 
            "repo": "https://github.com/z0z0r4/bing-wallpaper-api" , 
            "contact": {
                "qq": "3531890582",
                "email": "z0z0r4@outlook.com"
            }}

@api.get("/regions", description="返回所有地区")
@add_ststus
async def get_regions():
    '''
    返回所有地区
    '''
    return region_list

@api.get("/region/{region}", description="返回对应地区壁纸信息")
@add_ststus
async def get_region(region: str, pn: int = 1, ps: int = 8):
    '''
    返回对应地区全部壁纸信息
    '''
    if ps >= 10:
        raise Exception("每页数量不能大于10！")
    if pn <= 0:
        raise Exception("页码不能小于1！")
    if region not in region_list:
        raise Exception("地区不存在！")
    with Session(bind=sql_engine) as sess:
        all_res = sess.query(sql_tables[region]).order_by(sql_tables[region].c.date.desc()).limit(ps).offset((pn-1)*ps).all()
    return {"data": [{"hsh": res[0], "date": res[1], "url": res[2], "urlbase": res[3], "title": res[4], "copyright": res[6]} for res in all_res], 
            "count": len(all_res),
            "pn": pn,
            "ps": ps}

@api.get("/region/{region}/{date}", description="返回对应地区该日壁纸信息，日期格式：YYYYMMDD")
@add_ststus
async def get_wallpaper_with_region_by_date(region: str, date: int = int(datetime.now().strftime("%Y%m%d"))):
    '''
    返回对应地区壁纸信息
    '''
    if region not in region_list:
        raise Exception("地区不存在！")
    with Session(bind=sql_engine) as sess:
        res = sess.query(sql_tables[region]).filter(sql_tables[region].c.date == date).first()
    if res:
        return {"hsh": res[0], "date": res[1], "url": res[2], "urlbase": res[3], "title": res[4], "copyright": res[6]}
    else:
        raise Exception("未能找到该壁纸！")

@api.get("/date", description="返回对应日期各地区壁纸信息，日期格式：YYYYMMDD")
@add_ststus
async def get_date(date: int = int(datetime.now().strftime("%Y%m%d"))):
    with Session(bind=sql_engine) as sess:
        result = {}
        for table in region_list:
            res = sess.query(sql_tables[table]).filter(sql_tables[table].c.date == date).first()
            if res:
                result[table] = {"hsh": res[0], "date": res[1], "url": res[2], "urlbase": res[3], "title": res[4], "copyright": res[6]}
            else:
                result[table] = None
    return {"date": date, "data": result}

if __name__ == "__main__":
    uvicorn.run(api, host=conf["apihost"], port=conf["apiport"])