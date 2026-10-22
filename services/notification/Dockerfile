FROM composer:2.8 AS vendor

WORKDIR /app
COPY services/notification/composer.json services/notification/composer.lock ./
RUN composer install \
    --no-dev \
    --no-interaction \
    --no-progress \
    --no-scripts \
    --ignore-platform-req=ext-pcntl \
    --prefer-dist \
    --optimize-autoloader

FROM ghcr.io/mrsuner/php-runtime:8.4.27-fpm-alpine3.24-20261021@sha256:e947dbecce00902c4a76d63afc902ddcb880ffa6227273167f00d4170a8a4033

ENV APP_ENV=production \
    APP_DEBUG=false

WORKDIR /app

RUN apk add --no-cache libpq libzip oniguruma \
    && apk add --no-cache --virtual .build-deps $PHPIZE_DEPS curl-dev libpq-dev libzip-dev oniguruma-dev \
    && docker-php-ext-install curl mbstring opcache pcntl pdo_pgsql posix zip \
    && pecl install redis-6.3.0 \
    && docker-php-ext-enable redis \
    && apk del .build-deps

COPY --from=vendor /app/vendor ./vendor
COPY services/notification ./

RUN chmod +x docker-entrypoint.sh \
    && chown -R www-data:www-data storage bootstrap/cache

USER www-data

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["php", "artisan", "horizon"]
