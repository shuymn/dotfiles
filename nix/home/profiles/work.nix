{ pkgs, ... }:

{
  home.packages = with pkgs; [
    acli
    circleci-cli
    colima
    docker
    docker-buildx
    docker-compose
    grpcurl
    phpactor
    watch
  ];
}
