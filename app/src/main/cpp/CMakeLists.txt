# Compilation NDK des deux bibliothèques natives du moteur.

cmake_minimum_required(VERSION 3.22.1)
project(taqbaylit_natif CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(AMONT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../natif/amont)
set(PONTS ${CMAKE_CURRENT_SOURCE_DIR}/../../../../natif)

# ----------------------------------------------------------------- KenLM
file(GLOB KENLM_UTIL   ${AMONT}/kenlm/util/*.cc)
file(GLOB KENLM_DBLCNV ${AMONT}/kenlm/util/double-conversion/*.cc)
file(GLOB KENLM_LM     ${AMONT}/kenlm/lm/*.cc)
list(FILTER KENLM_UTIL   EXCLUDE REGEX ".*(main|test)\\.cc$")
list(FILTER KENLM_DBLCNV EXCLUDE REGEX ".*(main|test)\\.cc$")
list(FILTER KENLM_LM     EXCLUDE REGEX ".*(main|test)\\.cc$")

add_library(kenlmjni SHARED
    ${PONTS}/kenlm_jni.cc
    ${KENLM_UTIL} ${KENLM_DBLCNV} ${KENLM_LM})

target_include_directories(kenlmjni PRIVATE ${AMONT}/kenlm)
target_compile_definitions(kenlmjni PRIVATE KENLM_MAX_ORDER=6 NDEBUG)
target_compile_options(kenlmjni PRIVATE -O2 -w -fexceptions)
# zlib est fourni par le NDK : KenLM s'en sert pour lire les modèles
# compressés, et l'édition de liens échoue sans lui.
target_link_libraries(kenlmjni log z)

# -------------------------------------------------------------- CRFsuite
file(GLOB CRF_SRC  ${AMONT}/crfsuite/lib/crf/src/*.c)
file(GLOB CQDB_SRC ${AMONT}/crfsuite/lib/cqdb/src/*.c)
file(GLOB LBFGS_SRC ${AMONT}/liblbfgs/lib/*.c)

add_library(crfjni SHARED
    ${PONTS}/crf_jni.cc
    ${CRF_SRC} ${CQDB_SRC} ${LBFGS_SRC})

# config.h minimal, déposé par le script de préparation
target_include_directories(crfjni PRIVATE
    ${PONTS}/config
    ${AMONT}/crfsuite/include
    ${AMONT}/crfsuite/lib/cqdb/include
    ${AMONT}/crfsuite/lib/crf/src
    ${AMONT}/liblbfgs/include)
target_compile_options(crfjni PRIVATE -O2 -w)
set_source_files_properties(${CRF_SRC} ${CQDB_SRC} ${LBFGS_SRC}
    PROPERTIES LANGUAGE C COMPILE_FLAGS "-std=gnu99")
target_link_libraries(crfjni log m)
