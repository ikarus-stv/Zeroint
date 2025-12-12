import requests

url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

payload={
  'scope': 'GIGACHAT_API_PERS'
}
headers = {
  'Content-Type': 'application/x-www-form-urlencoded',
  'Accept': 'application/json',
  'RqUID': '019afee3-9e4a-7344-8254-fca1ccc83aea',
  'Authorization': 'Basic <55718f58-b861-46e5-90a7-46f4c2cf00ef>'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)