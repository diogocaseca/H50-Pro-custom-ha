# Changelog

## 0.5.0

- Zonas no mapa do Início: o modo **Desenhar zona** deu lugar ao botão **+ Zona**, que põe um retângulo de
  1,5 × 1,5 m no meio da parte visível do mapa. Arraste a zona para movê-la e um canto para mudar o tamanho.
- Com zoom, arrastar fora das zonas move o mapa (antes, no modo desenho, todo arrasto virava uma zona nova).
- Com zonas na seleção, tocar num cômodo não desfaz mais as zonas sem querer.
- Zona salva aparece só para ver: não dá para mover nem redimensionar.

## 0.4.9

- Correção: o percurso do robô no mapa (Início e Histórico) aparecia cortado, só com as curvas. O H50 Pro grava só os
  pontos onde muda de direção, e o painel não ligava pontos a mais de 1 m um do outro, então as faixas retas da limpeza
  sumiam. Agora os pontos de limpeza são sempre ligados; a regra de 1 m vale só para o deslocamento (o salto da base
  até a área continua sem linha).

## 0.4.8

- Correção: a conexão local caía para a nuvem a cada poucos minutos. Bastava uma resposta perdida do robô (normal no
  Wi-Fi, mesmo com sinal cheio) para o painel passar 60 s na nuvem, e um comando nessa janela podia ser aceito pela
  nuvem sem chegar ao robô. Agora a leitura tenta de novo pela rede local antes de ir para a nuvem.
- Antes de cada comando, o painel testa a rede local, mesmo dentro da janela da nuvem; só manda pela nuvem se ela não
  responder.
- Depois de um comando de limpeza, o painel confere se o robô saiu da base. Se não sair em 1 minuto, mostra um aviso
  ("aceitou o comando mas não saiu da base") e grava no Registro do app.
- Diagnóstico → Comandos enviados: colunas **Via** (rede local ou nuvem) e **Confirmado**.

## 0.4.7

- Painel: a linha **Progresso da secagem** do Estado do robô e o aviso **Secando** do Início mostram a porcentagem
  calculada pela duração e pelos minutos restantes, como o sensor do MQTT (antes ficavam em 0 %).

## 0.4.6

- Correção: o sensor **Progresso da secagem** ficava em 0 %. O H50 Pro não preenche a porcentagem da secagem (2/88);
  agora ela é calculada pela **Duração da secagem** (2 h, 3 h ou 4 h) e pelos **minutos restantes**. Se o robô
  passar a informar a porcentagem, vale a dele.

## 0.4.5

- MQTT: sensor binário **Secagem em andamento**, ligado enquanto a base seca os mops e desligado quando a secagem
  termina ou é parada. Bom para automações de "começou a secar" e "terminou de secar".

## 0.4.4

- O limite de zonas desenhadas saiu do cartão próprio e foi para a **tabela de ajustes** da aba Configurações, grupo
  **Sistema** (item "Limite de zonas desenhadas por limpeza"). O valor salvo continua valendo.

## 0.4.3

- O **limite de zonas desenhadas** saiu da configuração do app e foi para a aba **Configurações** do painel, cartão
  **Limpeza por zona** (padrão 3, de 1 a 10, só o administrador muda). A opção `zone_limit` do app deixa de existir.

## 0.4.2

- Nova opção **`zone_limit`** (padrão 3, de 1 a 10): quantas zonas dá para desenhar no mapa por limpeza e salvar
  numa zona com nome (patch 0011). Também vale para o `clean_zones` do MQTT com coordenadas. Rotinas do app Xiaomi
  Home e zonas já salvas não são afetadas.

## 0.4.1

- **Zoom no mapa do Início** (patch 0010): botões **+**, **−** e **⟲** sobre o mapa, pinça com dois dedos no celular e
  **Ctrl + rodinha** no computador, até 5×. Com zoom, arrastar move o mapa; no modo "Desenhar zona", um dedo desenha e
  dois movem e ampliam.

## 0.4.0

- **Limpeza por zona** (patch 0009): **Desenhar zona** no mapa do Início (até 10 retângulos por limpeza) e **zonas com
  nome** no menu Área (só o administrador salva e apaga; o nome não pode repetir o de outra zona nem o de uma rotina).
- Rotinas por zonas rodam pelo painel: as zonas são aprendidas quando a rotina roda pelo app Xiaomi Home. Rotina que o
  painel não consegue rodar fica com o ▶ desabilitado e o motivo embaixo do nome.
- MQTT: botões **Rotina: …** e **Zona: …** no dispositivo, e o comando `clean_zones` (`zone` ou `zones`).
- Sai o cartão **Teste: limpeza por zona** (o comando foi confirmado no H50 Pro).

## 0.3.9

- MQTT: sensor **Secagem restante** (minutos que faltam para terminar a secagem dos mops).

## 0.3.8

- MQTT: sensor **Progresso da secagem** (% da secagem dos mops na base).

## 0.3.7

- Teste: cartão **Teste: limpeza por zona** no Início (administrador e operador). Lista as zonas das últimas limpezas
  por zona feitas pelo app Xiaomi Home e manda o robô limpar uma delas pela rede local, para descobrir se o H50 Pro
  aceita o comando de zona (patch 0008). Só com o robô na base.

## 0.3.6

- MQTT: sensor binário **Limpeza em andamento**, ligado do início ao fim da limpeza. Pausas e idas à base no meio da
  limpeza (lavar o mop, recarregar para continuar) não o desligam; desliga quando o robô volta à base no fim. Bom para
  automações de "começou" e "terminou". O log do app registra "limpeza começou/terminou".

## 0.3.5

- Correção: ao executar uma rotina pelo painel (▶ no Início) ou pelo MQTT (`custom`), o robô usava o **modo de
  limpeza atual** em vez do modo da rotina. Uma rotina "só aspirar" podia sair com pano e voltar à base para lavar
  os mops. Agora o modo da rotina é ajustado antes de limpar (patch 0007).
- Rotina com modos diferentes por cômodo (aspira uns, passa pano em outros) é recusada com uma mensagem: rode-a pelo
  app Xiaomi Home.

## 0.3.4

- MQTT: sai o sensor **Detergente** (o H50 Pro não tem reservatório de detergente). A entidade é removida do HA na
  atualização.

## 0.3.3

- MQTT: seletores **Caminho** (Rápido, Padrão, Profunda) e **Tempos de limpeza** (Uma vez, Duas vezes) nas
  configurações do dispositivo, como na tela "Selecionar modo" do painel.

## 0.3.2

- MQTT: seletor **Potência de sucção** (Silencioso, Padrão, Intenso, Turbo) nas configurações do dispositivo, ao lado
  de Modo de limpeza e Nível de água do mop. A potência continua também no próprio aspirador.

## 0.3.1

- MQTT: opções `mqtt_user`, `mqtt_password`, `mqtt_port` (padrão 1883) e `mqtt_host` (vazio = Mosquitto do HA).
- Correção: com a rede do host, o app não resolve o nome `core-mosquitto` que o Supervisor informa; agora usa
  `127.0.0.1` nesse caso. Falhas de conexão com o broker (host, porta, usuário/senha) passam a aparecer no Registro.

## 0.3.0

- O painel aparece para **todos** os usuários do Home Assistant (`panel_admin: false`), com perfil pelo usuário do HA:
  administradores do HA e os logins da nova opção `admins` entram como administrador; os demais, como **operador**
  (comanda o robô e escolhe os modos da limpeza, sem mexer em configurações) ou somente leitura (opção `others`).
- **Atenção ao atualizar:** se o seu Supervisor ainda não informa o grupo do usuário, você entra como operador até
  colocar o seu login em `admins` (aba Configuração do app). O Registro do app mostra o login de quem abriu o painel.
- Patch `0006`: perfil operador e perfis pelo usuário do Ingress (`H50_INGRESS_ADMINS`, `H50_INGRESS_OTHERS`), com testes.

## 0.2.0

- Integração MQTT (opção `mqtt`, desligada por padrão): cada robô vira um dispositivo do Home Assistant por MQTT
  discovery, com aspirador (inclusive limpeza por cômodo), bateria, status, progresso, área, tempo, falha,
  consumíveis, tanques, carregando, conectividade, modo de limpeza, nível de água e botões da base. Usa o broker do
  app Mosquitto (dados vindos do Supervisor) e continua 100% local.
- Patch `0005`: `H50_API_TOKEN` no painel (token de administrador aceito só de `127.0.0.1`), com testes.
- `run.py` carrega as variáveis do container (s6-overlay) e não grava `__pycache__` em `/data`.

## 0.1.2

- Opção `cloud_region` (servidor da nuvem Xiaomi: `auto`, `us`, `de`, `sg`, `cn`, `ru`, `i2`) para contas com aparelhos
  em servidores diferentes: com o servidor do robô fixo, o mapa e o cadastro pela conta voltam a funcionar.
- Patch `0004`: `H50_CLOUD_COUNTRY` no painel (vazio ou `auto` = comportamento original), com testes.

## 0.1.1

- Watchdog do Supervisor: checagem TCP da porta 8050; com o interruptor **Watchdog** ligado, o HA reinicia o app se o
  painel parar de aceitar conexões (o reinício quando o processo cai já funcionava).

## 0.1.0

- Primeira versão como app do Home Assistant: painel na barra lateral via Ingress (login e HTTPS do HA),
  rede do host para falar com o robô em UDP 54321, dados em `/data` (incluídos no backup do HA).
- Opções: senha e senha somente leitura do acesso direto, acesso direto pela porta 8050 (desligado por padrão), nível de log.
- Código: [nathanabreu/H50-Pro-custom@b982e72](https://github.com/nathanabreu/H50-Pro-custom/commit/b982e7294ce5e546d5ec67c17bc3d97902365864)
  com os patches:
  - `0001` front com caminhos relativos (funciona atrás de um prefixo, como o do Ingress);
  - `0002` redirecionamento relativo para o login;
  - `0003` modo Ingress opt-in (`H50_INGRESS`, `H50_INGRESS_ONLY`) e `H50_LOG_LEVEL`, com testes.
