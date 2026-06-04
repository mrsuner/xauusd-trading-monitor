FROM node:22-alpine AS build

WORKDIR /app

COPY apps/dashboard-web/package*.json ./
RUN npm install

COPY apps/dashboard-web ./
RUN npm run build

FROM nginx:1.27-alpine

COPY apps/dashboard-web/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY apps/dashboard-web/docker/entrypoint.sh /entrypoint.sh
COPY --from=build /app/dist /usr/share/nginx/html

RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
