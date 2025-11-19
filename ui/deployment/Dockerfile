#FROM  registry.access.redhat.com/ubi9/nodejs-18-minimal as build
FROM  registry.access.redhat.com/ubi9/nodejs-22 as build

ENV NODE_ENV=production

#create a working folder
WORKDIR /ui

RUN npm install -g npm
RUN npm --version
#install pnpm via corepack (can be done via npmn as well instead)
RUN npm install -g corepack
RUN corepack enable                         
RUN corepack prepare pnpm@latest --activate # Install pnpm via Corepack

#copy the entire project to the working folder
COPY . .
# Install all dependencies (including devDependencies needed for the build).
# `--frozen-lockfile` ensures reproducible builds based on pnpm-lock.yaml.
RUN pnpm install --frozen-lockfile

# Run our combined build command.
# As per your package.json, this builds:
# - Frontend (Vite) to /ui/build
RUN pnpm build



FROM registry.access.redhat.com/ubi9/nginx-120 as serve

USER root
#Install debugging tools ( telnet is out-of-ubi9 for nginx ncat instead)
RUN dnf update -y && dnf install -y vim less iputils nmap-ncat && dnf clean all

# Copy and set permissions for entrypoint.sh while still root
COPY /deployment/entrypoint.sh /opt/app-root/src/entrypoint.sh
RUN chmod +x /opt/app-root/src/entrypoint.sh
RUN chmod -R 7777 /opt/app-root/src/
RUN chown default:root /opt/app-root/src/

#copy certificate files from the cred repo
COPY genie-cred-data/certificates/* /etc/nginx/ssl/

COPY --from=build /ui/build /usr/share/nginx/html
RUN chown -R default:root /usr/share/nginx/html && chmod -R 775 /usr/share/nginx/html
COPY deployment/nginx.conf.template /etc/nginx/nginx.conf.template

USER default

EXPOSE 8080
EXPOSE 443

ENTRYPOINT ["/opt/app-root/src/entrypoint.sh"]
