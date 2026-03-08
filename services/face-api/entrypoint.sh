#!/bin/sh
set -eu

runtime_dir="${QAONGDUR_FACE_RUNTIME_DIR:-/runtime}"
site_packages_dir="${runtime_dir}/site-packages"
bootstrap_error_file="${QAONGDUR_FACE_BOOTSTRAP_ERROR_FILE:-${runtime_dir}/bootstrap-error.txt}"
inspireface_repo="${QAONGDUR_FACE_INSPIREFACE_REPO:-/mnt/inspireface}"

mkdir -p "${runtime_dir}" "${site_packages_dir}"
rm -f "${bootstrap_error_file}"

record_bootstrap_error() {
  printf '%s\n' "$1" > "${bootstrap_error_file}"
}

bootstrap_inspireface() {
  if [ -f "${site_packages_dir}/inspireface/__init__.py" ] && [ -f "${site_packages_dir}/inspireface/modules/core/libs/linux/x64/libInspireFace.so" ]; then
    echo "InspireFace runtime already bootstrapped."
    return 0
  fi

  if [ ! -f "${inspireface_repo}/CMakeLists.txt" ]; then
    record_bootstrap_error "InspireFace repo not found at ${inspireface_repo}"
    return 0
  fi

  build_src_dir="${runtime_dir}/build-src"
  build_dir="${runtime_dir}/build"
  lib_target_dir="${build_src_dir}/python/inspireface/modules/core/libs/linux/x64"
  job_count="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"

  echo "Bootstrapping InspireFace from ${inspireface_repo}"
  rm -rf "${build_src_dir}" "${build_dir}"
  mkdir -p "${build_src_dir}" "${build_dir}"
  cp -a "${inspireface_repo}/." "${build_src_dir}/"

  if ! cmake -S "${build_src_dir}" -B "${build_dir}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DISF_BUILD_WITH_SAMPLE=OFF \
    -DISF_BUILD_WITH_TEST=OFF \
    -DISF_ENABLE_BENCHMARK=OFF \
    -DISF_ENABLE_USE_LFW_DATA=OFF \
    -DISF_ENABLE_TEST_EVALUATION=OFF \
    -DISF_BUILD_SHARED_LIBS=ON; then
    record_bootstrap_error "Failed to configure InspireFace with CMake."
    return 0
  fi

  if ! cmake --build "${build_dir}" -j"${job_count}"; then
    record_bootstrap_error "Failed to build InspireFace runtime library."
    return 0
  fi

  mkdir -p "${lib_target_dir}"
  if [ ! -f "${build_dir}/lib/libInspireFace.so" ]; then
    record_bootstrap_error "Built InspireFace library was not found in ${build_dir}/lib."
    return 0
  fi
  cp "${build_dir}/lib/libInspireFace.so" "${lib_target_dir}/libInspireFace.so"

  python -m pip install --target "${site_packages_dir}" --upgrade \
    numpy \
    opencv-python-headless \
    loguru \
    filelock
  if ! python -m pip install --target "${site_packages_dir}" --no-deps "${build_src_dir}/python"; then
    record_bootstrap_error "Failed to install the InspireFace Python package."
    return 0
  fi
}

bootstrap_inspireface

export PYTHONPATH="${site_packages_dir}:/app/src"
exec uvicorn face_api.main:app --app-dir /app/src --host 0.0.0.0 --port 8020
