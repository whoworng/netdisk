# --- 阶段一：编译环境 (Builder) ---
FROM nginx:1.26.1-alpine AS builder

# 1. 替换为国内镜像源 (清华源)
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories

# 2. 安装编译所需的依赖
RUN apk add --no-cache \
    gcc \
    libc-dev \
    make \
    openssl-dev \
    pcre2-dev \
    zlib-dev \
    linux-headers \
    libtool \
    automake \
    autoconf \
    git \
    g++ \
    cmake \
    zstd-dev \
    brotli-dev

# 3. 更换更稳定的代理地址，并设置 Git 缓冲区
RUN git config --global url."https://ghfast.top/https://github.com/".insteadOf "https://github.com/" && \
    git config --global http.postBuffer 524288000

# 4. 下载当前镜像对应版本的 Nginx 源码
RUN NGINX_VERSION=$(nginx -v 2>&1 | cut -d '/' -f 2) && \
    wget http://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz && \
    tar zxvf nginx-${NGINX_VERSION}.tar.gz

# 5. 克隆模块源码
RUN git clone --depth 1 --recursive https://github.com/google/ngx_brotli.git
RUN git clone --depth 1 --recursive https://github.com/tokers/zstd-nginx-module.git

# 6. 编译动态模块
# 使用 eval 确保 CONFARGS 中的引号被正确解析
WORKDIR /nginx-1.26.1
RUN CONFARGS=$(nginx -V 2>&1 | grep "configure arguments:" | sed 's/configure arguments: //') && \
    eval "./configure $CONFARGS --add-dynamic-module=/ngx_brotli --add-dynamic-module=/zstd-nginx-module" && \
    make modules


# --- 阶段二：运行环境 (Runtime) ---
FROM nginx:1.26.1-alpine
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apk/repositories
RUN apk add --no-cache zstd-libs brotli-libs
COPY --from=builder /nginx-1.26.1/objs/ngx_http_brotli_filter_module.so /usr/lib/nginx/modules/
COPY --from=builder /nginx-1.26.1/objs/ngx_http_brotli_static_module.so /usr/lib/nginx/modules/
COPY --from=builder /nginx-1.26.1/objs/ngx_http_zstd_filter_module.so /usr/lib/nginx/modules/
COPY --from=builder /nginx-1.26.1/objs/ngx_http_zstd_static_module.so /usr/lib/nginx/modules/
COPY conf/nginx.conf /etc/nginx/nginx.conf
COPY html /usr/share/nginx/html
