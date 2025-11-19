## Building the UI

When building the UI, we currently work with a lock file. This allows us to keep working in the same environment without constant synchronization of development environments. In addition, it makes the production build more stable (as we only lock after a successful build). If a change needs to be made to one of the packages, the developer in question is responsible for removing the lock file and installing the modules anew using the updated `package.json`. This means the developer will have to resolve all issues with packages/modules versions prior to merging into the `main` branch.

### Prerequisites

PNPM installed on your system.

* Upgrade your npm:
    `npm install -g npm`

* Install PNPM via Corepack (can be done via npm as well instead):
    `npm install -g corepack`
    `corepack enable`

* Install PNPM via Corepack:
    `corepack prepare pnpm@latest --activate`

### Install all Required Packages and Build

* Make sure you have the `package.json` and `pnpm-lock.yaml` files in place. These should come with the cloning and should be under the UI's main folder.
    **NOTE: IF YOU NEED TO ADD A NEW PACKAGE, YOU MUST UPDATE THE `PACKAGE.JSON` FILE, INSTALL PACKAGES, AND YOU MUST PUSH THE NEW LOCK FILE AS WELL AFTER VERIFYING THE BUILD IS WORKING.**

* Install all dependencies (including devDependencies needed for the build). `--frozen-lockfile` ensures reproducible builds based on `pnpm-lock.yaml`.
    The lock file is the output of the last successful installation, and we should use it unless we specifically need to change packages or versions.
    `pnpm install --frozen-lockfile`

* Build the UI:
    `pnpm build`

## Running the UI (Locally)

As we usually use existing backends or local ones depending on our work, we need a quick method to change the backends we run against. Until now, we used to update Axios config. This works properly but with some caveats:
1.  The changes must be removed before building the code so that Axios won't change the UI behavior.
2.  Every change needs a rebuild if we want to check the UI as a package.
3.  If we need to have a common API structure, this might be complicated.

Instead of using Axios, we need to change the usage to `vite.config.ts` proxies. This is built for the development environment. The `vite.config.ts` isn't going into the code, so it's safe to build it. That way, if Axios already has some config, we just need to adjust the config to fit it (just like Nginx config).

In order to run the UI locally, follow these steps:

1.  Update the `vite.config.ts` server/proxy section to route the requests properly to the backends and replace the api1/api2 from the UI. This step is crucial as it simulates the Nginx behavior that we use in production (see example below):

    ```
    server: {
      port: 5173, // Or whatever port Vite is running on by default
      proxy: {
        // Proxy for api1
        '/api1': {
          target: 'http://<dataflow_be_address>:<dataflow_be_port>',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api1/, '/api'), // This rewrites /api1 to /api
          secure: false, // Set to true for production if target is HTTPS and has valid cert.
                        // Set to false for dev if you're getting SSL errors with self-signed or invalid certs.
        },
        // Proxy for api2 (assuming this is still local or another service)
        '/api2': {
          target: 'http://<multiagent_be_address>:<multiagent_be_port>',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api2/, '/api'), // This rewrites /api2 to /api
          // secure: false, // Only needed if this target is HTTPS and you have SSL issues
        },
        // You can add more proxies here if needed
      }
    },
    ```

## Analyzing the UI Build (Optional)

In order to analyze the UI build bundle, we need a build analyzer tool. Since Vite (the tool for building and serving) is using Rollup, we can use the `rollup-plugin-visualizer`.

1.  Start by installing the plugin:
    `pnpm add -D rollup-plugin-visualizer`

**NOTE: Currently, Vite is being enabled only when building locally (when the NODE_ENV environment variable is not set to 'production'). In order to run the analyzer, set the environment variable `NODE_ENV="development"`. After the build, a new file will be created and opened automatically, analyzing the bundle of the UI.**

## Appendixes

### UI Building Infra

#### Tools
* PNPM - Package manager
* Vite - Code building and serving tool

#### Important Files

* `package.json`

    Includes all packages needed for our app.
    Includes a `scripts` part. In this part, when we run a builder/installer, it goes to the `scripts` part, and if the arguments are there, it takes them.
    For example:

    ```
    "scripts": {
      "build:frontend": "vite build",
      "build": "pnpm run build:frontend",
    }
    ```

    When we run `pnpm build` or `pnpm run build`, it first goes to the `scripts` part and sees that it needs to run the command: `pnpm run build:frontend`, which in turn changes `build:frontend` to `vite build`. So, the actual final command is `vite build`.
    NOTE: If your script line includes `pnpm run <command>`, this will send PNPM again to the `scripts` part to look for a line named `<command>`.

* `pnpm-lock.yaml`

    Lock files are more specific package dependency files. In `package.json`, we usually give a range or general rules as to what versions are allowed/required. But when we actually install the packages, we get specific versions. This is listed in the lock files, and it allows us to use them as the base for future installations and prevent conflicts and problems due to version issues.

    In our case, since we use PNPM, the lock file to use is `pnpm-lock.yaml`.

    **NOTE: If you need to update a package and reinstall, you'll need to update the lock file (or run `install` to overwrite the lock file and push it after install + build are successful).**

* `vite.config.ts`

    As we use Vite as the build tool, we need to have the Vite configuration file set. In it, we set the input/output folders, proxies, and plugins we want to use during our build. The syntax is TypeScript.