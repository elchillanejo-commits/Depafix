#!/bin/bash
source ~/.env_telegram
while true; do
  OFFSET=$(curl -s "https://api.telegram.org/bot$TOKEN/getUpdates" | jq -r '.result[-1].update_id + 1 // 0')
  UPDATE=$(curl -s "https://api.telegram.org/bot$TOKEN/getUpdates?offset=$OFFSET" | jq -r '.result[-1]')
  MSG=$(echo $UPDATE | jq -r '.message.text')
  CHAT_ID=$(echo $UPDATE | jq -r '.message.chat.id')
  
  if [[ "$MSG" == "saldo" ]]; then
    curl -s "https://api.telegram.org/bot$TOKEN/sendMessage?chat_id=$CHAT_ID&text=Tokens: $(cat ~/.tokens_estudio)"
  elif [[ "$MSG" == "/aquiles" ]]; then ./agente_aquiles.sh;
  elif [[ "$MSG" == "/siegfried" ]]; then ./agente_siegfried.sh;
  elif [[ "$MSG" == "/sancho" ]]; then ./agente_sancho.sh;
  fi
  sleep 10
done
