FROM caddy:2

COPY Caddyfile /etc/caddy/Caddyfile

EXPOSE 8080

ENTRYPOINT ["caddy"]
CMD ["run", "--config", "/etc/caddy/Caddyfile"]
