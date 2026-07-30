# syntax=docker/dockerfile:1.4

# 1. For build React app
FROM node:22-alpine AS development
# Set working directory
WORKDIR /app
RUN echo $NGINX_FILE

# 
COPY package.json package.json
COPY package-lock.json package-lock.json

# Same as npm install
RUN npm ci

COPY . .

ENV CI=true
ENV PORT=3000

CMD [ "npm", "start" ]

FROM development AS build

RUN npm run build

# 2. For Nginx setup
FROM nginx:alpine

WORKDIR /usr/share/nginx/html
#COPY --from=build /app/nginx/local_nginx.conf /etc/nginx/conf.d/default.conf

# Remove default nginx static assets
RUN rm -rf ./*

# Copy static assets from builder stage
COPY --from=build /app/build .

ENTRYPOINT ["nginx", "-g", "daemon off;"]