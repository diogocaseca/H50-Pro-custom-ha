# Changelog

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
