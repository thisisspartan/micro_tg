#!/bin/bash

REGISTRY="http://registry.local:30500"

# Получаем список всех репозиториев
repos=$(curl -s "$REGISTRY/v2/_catalog" | jq -r '.repositories[]')

# Перебираем каждый репозиторий и получаем теги
for repo in $repos; do
    tags=$(curl -s "$REGISTRY/v2/$repo/tags/list" | jq -r '.tags[]?')
    for tag in $tags; do
        echo "$repo:$tag"
    done
done
