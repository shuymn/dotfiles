{ pkgs, ... }:

{
  home.packages = with pkgs; [
    awscli2
    circleci-cli
    colima
    docker
    docker-buildx
    docker-compose
    granted
    grpcurl
    watch
  ];
}
