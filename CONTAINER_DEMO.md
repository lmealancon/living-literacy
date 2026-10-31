# Containerized local synthetic demo

This is a localhost-only development demonstration, not a real-child or production deployment. Parent identities, guardian authority, consent and curriculum review are simulated. Do not enter real personal information. No real authentication provider, production database, TLS or vetted release controls are configured.

Requires Docker Engine and Compose v2. Optionally copy `.env.example` to `.env` to set the documented local runtime option; no credentials belong in that file. From this directory, build the image and initialize an empty persistent demo database with a fictional passphrase of at least 12 characters:

```sh
docker compose build
docker compose run --rm living-literacy --db /data/demo.sqlite3 --init
```

Initialization is interactive; it prompts for the fictional passphrase, without putting it in the image, Compose file, shell command or environment. Existing databases are not overwritten. The default identity is `synthetic-parent-1`. Start the server:

```sh
docker compose up -d
```

Open `http://127.0.0.1:8765` on the **same computer running Docker**, and sign in using the fictional identity and passphrase. Stop with `docker compose down`; the named volume preserves synthetic data. Back up that volume before changing it; do not remove the volume if you want to retain the synthetic data.

The server ordinarily binds to loopback. The Compose command explicitly opts into a container-network listener because port publishing cannot reach container loopback. Compose publishes the port only to the host loopback and uses a dedicated internal network; Host and Origin checks still require `127.0.0.1:8765`. Other processes on the host, Docker administrators, or containers joined to the same Docker network can reach the service. Docker/firewall behavior varies across hosts and versions; verify your host's port bindings. Do not change the port binding to a public interface, attach untrusted containers, or deploy this service on the Internet. These measures do not make the application safe for real users or student data.
