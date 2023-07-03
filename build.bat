docker login -u fabbro03 -p dckr_pat_eswkLGlfMmfY2h8I4GD9j4p7WoQ
docker buildx build --push --platform linux/amd64,linux/arm/v7 --tag fabbro03/solar-simulator .