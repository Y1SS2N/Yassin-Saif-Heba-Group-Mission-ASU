# generated from ament/cmake/core/templates/nameConfig.cmake.in

# prevent multiple inclusion
if(_erc_nav_benchmark_CONFIG_INCLUDED)
  # ensure to keep the found flag the same
  if(NOT DEFINED erc_nav_benchmark_FOUND)
    # explicitly set it to FALSE, otherwise CMake will set it to TRUE
    set(erc_nav_benchmark_FOUND FALSE)
  elseif(NOT erc_nav_benchmark_FOUND)
    # use separate condition to avoid uninitialized variable warning
    set(erc_nav_benchmark_FOUND FALSE)
  endif()
  return()
endif()
set(_erc_nav_benchmark_CONFIG_INCLUDED TRUE)

# output package information
if(NOT erc_nav_benchmark_FIND_QUIETLY)
  message(STATUS "Found erc_nav_benchmark: 1.0.0 (${erc_nav_benchmark_DIR})")
endif()

# warn when using a deprecated package
if(NOT "" STREQUAL "")
  set(_msg "Package 'erc_nav_benchmark' is deprecated")
  # append custom deprecation text if available
  if(NOT "" STREQUAL "TRUE")
    set(_msg "${_msg} ()")
  endif()
  # optionally quiet the deprecation message
  if(NOT ${erc_nav_benchmark_DEPRECATED_QUIET})
    message(DEPRECATION "${_msg}")
  endif()
endif()

# flag package as ament-based to distinguish it after being find_package()-ed
set(erc_nav_benchmark_FOUND_AMENT_PACKAGE TRUE)

# include all config extra files
set(_extras "")
foreach(_extra ${_extras})
  include("${erc_nav_benchmark_DIR}/${_extra}")
endforeach()
