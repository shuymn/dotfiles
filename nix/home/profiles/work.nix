{ pkgs, ... }:

{
  home.packages = with pkgs; [
    agent-browser
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
