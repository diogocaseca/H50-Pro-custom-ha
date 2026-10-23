# Changelog

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
