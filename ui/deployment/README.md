## UI Deployment Overview

For UI deployment, we use an Nginx container to both serve the UI itself and route requests to the backends according to the URI path. In order to build the container, we use a two-stage Dockerfile: the first for creating the UI bundle, and the second for the actual runtime container.

## Building the UI Container

In order to build the UI container image, go to the UI folder (one level above the current folder) and run the commands below:

1.  `podman build -f deployment/Dockerfile -t <image_name> .`

2.  (Optional) `podman tag <image_name> <image_name_at_registry>`

3.  (Optional) `podman push <image_name_at_registry>`

**NOTE: When pushing the image to a registry, you need to make sure you're logged in to it; otherwise, the upload will fail.**

## Nginx Dynamic Configuration

Nginx doesn't support environment variables in its configuration files. To make the Nginx configuration dynamic, the common practice is to use a templating tool, most commonly `envsubst`. For that, we've created the `nginx.conf.template` in this folder. When the Nginx container starts, we first run the `envsubst` command, which creates the actual config file, and only after that do we start Nginx.
envsubst command example:

```bash envsubst '$VAR1,$VAR2' < nginx.conf.template > nginx.conf```

**NOTE: `nginx.conf` sometimes has internal parameters (for example: `$uri`) that are part of the regular work of Nginx (since URIs and traffic are dynamic). So, when templating the `.conf` file, you might have a `$uri` which shouldn't be replaced at all but stay as is for Nginx itself. However, `envsubst` goes over ALL occurrences that look like an environment variable (in that case, `$uri`) and tries to replace them. Since `uri` isn't being used as an environment variable, it will be empty. Thus, the `nginx.conf` will have a section like this:**
```
location / {
    try_files /index.html;
}
```
**instead of:**
```
location / {
    try_files $uri /index.html;
}
```
**In order to overcome this, there are two options: the first is to manually specify for `envsubst` all parameters which should be replaced; the second option is to replace the `$` which invokes `envsubst` with a string that will be later replaced to `$`. So the new section will look like the example below:**
```
location / {
    try_files ${DOLLAR}uri /index.html;
}
```
**so after replacement, the section will be correct.**


## Nginx Configuration Parameters

* **`proxy_pass`**: Will just redirect the call to the location set.
* **`rewrite`**: Works internally; Nginx will receive the call, change it according to the setting, and will resume sending the call to the new, updated location.
* **`return`**: Nginx will return the requested status (in this case, 3XX) and the URL the client needs to now redirect to.

In our case we used the `rewrite` options it causes the client to be aware of the address change as we've added a redirect flag.


**NOTE: A listener to the BE ports wasn't added as we don't use Nginx as the proxy for the backends directly, but only when going through the UI. the access to the backends is being done solely by the client after getting a redirect from the UI so the traffic doesn't go via the nginx in that case**

**NOTE: Using the `notebook` namespace means that routes/services aren't always available from outside the setup. Hence, use the `pipeline` or `runtime` namespace.**

## TBD

* Create a `.dockerignore` to not copy unneeded files/folders into the Docker image when building.