import requests
import json
import yagmail
import yaml
import os

# 通知模块（邮件和Server酱）
def MsgSend(mails, message_title, message_info, mail_receiver=False, sct_ftqq=False):
    if mails.get('mail_address'):
        try:
            mail = yagmail.SMTP(mails['mail_address'], mails['password'], mails['host'])
            mail.send(mail_receiver, message_title, message_info)
        except Exception as e:
            print("邮件推送出错！", str(e))
    if sct_ftqq:
        try:
            url = f'https://sctapi.ftqq.com/{sct_ftqq}.send?title={message_title}&desp={message_info}'
            requests.get(url)
        except Exception as e:
            print("微信推送出错！", str(e))

# 获取打卡数据（经纬度）
def GetPunchData(username, location, tencentKey):
    geocode = requests.get("https://apis.map.qq.com/ws/geocoder/v1", params={"address": location, "key": tencentKey})
    geocode_data = json.loads(geocode.text)
    if geocode_data['status'] == 0:
        reverseGeocode = requests.get("https://apis.map.qq.com/ws/geocoder/v1", params={"location": f"{geocode_data['result']['location']['lat']},{geocode_data['result']['location']['lng']}", "key": tencentKey})
        reverseGeocode_data = json.loads(reverseGeocode.text)
        if reverseGeocode_data['status'] == 0:
            location_data = reverseGeocode_data['result']
            PunchData = {
                "latitude": location_data['location']['lat'],
                "longitude": location_data['location']['lng'],
                "nationcode": "",
                "country": "中国",
                "province": location_data['ad_info']['province'],
                "citycode": "",
                "city": location_data['ad_info']['city'],
                "adcode": location_data['ad_info']['adcode'],
                "district": location_data['ad_info']['district'],
                "towncode": location_data['address_reference']['town']['id'],
                "township": location_data['address_reference']['town']['title'],
                "streetcode": "",
                "street": location_data['address_component']['street']
            }
            return PunchData
    return None

# 获取打卡日志（超星版）
def GetMySignLogs(headers):
    url = 'https://wzxy.chaoxing.com/dormSign/mobile/receive/getMySignLogs'
    params = {'page': 1, 'size': 10}
    res = requests.get(url, headers=headers, params=params)
    try:
        text = res.json()
        if text.get('code') == 0 and text.get('data'):
            data = text['data'][0]
            if int(data['signStatus']) != 1:
                print("用户已打过卡！")
                return False, False
            signId, id = data['signId'], data['id']
            return signId, id
        else:
            print(f"获取打卡日志失败，API返回: {text}")
            return False, False
    except Exception as e:
        print(f"解析打卡日志响应出错: {str(e)}, 原始响应: {res.text}")
        return False, False

# 提交打卡（超星版）
def Punch(headers, punchData, username, id, signId, mails, receive=False, sct_ftqq=False):
    headers['Referer'] = 'https://servicewechat.com/wxce6d08f781975d91/203/page-frame.html'
    url = 'https://wzxy.chaoxing.com/dormSign/mobile/receive/doSignByLocation'
    params = {'id': id, 'signId': signId}
    res = requests.post(url, data=json.dumps(punchData), headers=headers, params=params)
    try:
        txt = res.json()
        if txt.get('code') == 0:
            print(f"{username} 打卡成功！")
            MsgSend(mails, "打卡成功！", f"{username} 归寝打卡成功！", receive, sct_ftqq)
            return True
        else:
            print(f"{username} 打卡失败！{str(txt)}")
            MsgSend(mails, "打卡失败！", f"{username} 归寝打卡失败！{str(res.text)}", receive, sct_ftqq)
            return False
    except Exception as e:
        print(f"{username} 打卡异常！{str(e)}")
        return False

def GetConfigs(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        configs = yaml.safe_load_all(f.read())
    return configs

def main():
    current_path = os.path.abspath(__file__)
    config_path = os.path.join(os.path.dirname(current_path), 'cache', 'config.yaml')
    configs = GetConfigs(config_path)
    
    for config in configs:
        if 'jwsession' not in config:
            print("请先在 config.yaml 中配置 jwsession！")
            continue
            
        username = config.get('username', '用户')
        jws = config['jwsession']
        print(f"开始处理账号: {username}")
        
        # 构造请求头
        headers = {
            'Host': 'wzxy.chaoxing.com',
            'Connection': 'keep-alive',
            'Accept': 'application/json, text/plain, */*',
            "cookie": f'JWSESSION={jws}',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; WLZ-AN00 Build/HUAWEIWLZ-AN00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/86.0.4240.99 XWEB/4343 MMWEBSDK/20220903 Mobile Safari/537.36 MMWEBID/4162 MicroMessenger/8.0.28.2240(0x28001C35) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 miniProgram/wxce6d08f781975d91',
            'Content-Type': 'application/json;charset=UTF-8',
            'X-Requested-With': 'com.tencent.mm',
            'Referer': 'https://wzxy.chaoxing.com/h5/mobile/dormSign/0.3.82/index.html'
        }

        # 检查是否已经打卡
        signId, id = GetMySignLogs(headers)
        if not signId:
            print(f"账号 {username} 暂无需打卡或打卡列表获取失败。")
            continue

        # 获取打卡地址数据
        punchData = GetPunchData(username, config['location'], config['tencent_map'])
        if not punchData:
            print(f"账号 {username} 获取经纬度失败！请检查腾讯地图 Key。")
            continue

        # 执行打卡
        Punch(headers, punchData, username, id, signId, config, config.get('receive', False), config.get('sct_ftqq', False))

if __name__ == "__main__":
    main()
