cmake_minimum_required(VERSION 3.22.1)

project(d1_npu_probe LANGUAGES CXX)

add_library(d1_npu_probe SHARED nnapi_probe.cpp)

find_library(dl_library dl REQUIRED)

target_link_libraries(d1_npu_probe PRIVATE ${dl_library})
