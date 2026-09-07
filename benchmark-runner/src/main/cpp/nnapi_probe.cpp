#include <android/NeuralNetworks.h>
#include <dlfcn.h>
#include <jni.h>

#include <cstdint>
#include <limits>
#include <sstream>
#include <string>

namespace {

using GetDeviceCountFunction = int (*)(uint32_t*);
using GetDeviceFunction = int (*)(uint32_t, ANeuralNetworksDevice**);
using GetDeviceNameFunction = int (*)(const ANeuralNetworksDevice*, const char**);
using GetDeviceTypeFunction = int (*)(const ANeuralNetworksDevice*, int32_t*);
using GetDeviceVersionFunction = int (*)(const ANeuralNetworksDevice*, const char**);
using GetDeviceFeatureLevelFunction = int (*)(const ANeuralNetworksDevice*, int64_t*);

void throw_runtime_error(JNIEnv* env, const std::string& message) {
    jclass exception_class = env->FindClass("java/lang/RuntimeException");
    if (exception_class != nullptr) {
        env->ThrowNew(exception_class, message.c_str());
    }
}

template <typename Function>
Function load_function(void* library, const char* name) {
    return reinterpret_cast<Function>(dlsym(library, name));
}

std::string nnapi_error(const char* operation, int status, uint32_t index) {
    std::ostringstream message;
    message << operation << " failed with NNAPI status " << status;
    if (index != std::numeric_limits<uint32_t>::max()) {
        message << " at device index " << index;
    }
    return message.str();
}

}  // namespace

extern "C" JNIEXPORT jobjectArray JNICALL
Java_com_example_d1check_benchmarkrunner_NnapiDeviceProbe_nativeEnumerateDevices(
        JNIEnv* env,
        jobject /* this */) {
    void* library = dlopen("libneuralnetworks.so", RTLD_NOW | RTLD_LOCAL);
    if (library == nullptr) {
        const char* detail = dlerror();
        throw_runtime_error(
                env,
                std::string("Unable to load libneuralnetworks.so: ") +
                        (detail == nullptr ? "unknown error" : detail));
        return nullptr;
    }

    const auto get_device_count = load_function<GetDeviceCountFunction>(
            library, "ANeuralNetworks_getDeviceCount");
    const auto get_device = load_function<GetDeviceFunction>(
            library, "ANeuralNetworks_getDevice");
    const auto get_name = load_function<GetDeviceNameFunction>(
            library, "ANeuralNetworksDevice_getName");
    const auto get_type = load_function<GetDeviceTypeFunction>(
            library, "ANeuralNetworksDevice_getType");
    const auto get_version = load_function<GetDeviceVersionFunction>(
            library, "ANeuralNetworksDevice_getVersion");
    const auto get_feature_level = load_function<GetDeviceFeatureLevelFunction>(
            library, "ANeuralNetworksDevice_getFeatureLevel");

    if (get_device_count == nullptr || get_device == nullptr || get_name == nullptr ||
        get_type == nullptr || get_version == nullptr || get_feature_level == nullptr) {
        dlclose(library);
        throw_runtime_error(env, "Android NNAPI device discovery symbols are unavailable");
        return nullptr;
    }

    uint32_t device_count = 0;
    int status = get_device_count(&device_count);
    if (status != ANEURALNETWORKS_NO_ERROR) {
        dlclose(library);
        throw_runtime_error(
                env,
                nnapi_error("ANeuralNetworks_getDeviceCount", status,
                            std::numeric_limits<uint32_t>::max()));
        return nullptr;
    }
    if (device_count > static_cast<uint32_t>(std::numeric_limits<jsize>::max() / 5)) {
        dlclose(library);
        throw_runtime_error(env, "NNAPI returned too many devices");
        return nullptr;
    }

    jclass string_class = env->FindClass("java/lang/String");
    if (string_class == nullptr) {
        dlclose(library);
        return nullptr;
    }
    jobjectArray values = env->NewObjectArray(
            static_cast<jsize>(device_count * 5), string_class, nullptr);
    if (values == nullptr) {
        dlclose(library);
        return nullptr;
    }

    for (uint32_t index = 0; index < device_count; ++index) {
        ANeuralNetworksDevice* device = nullptr;
        const char* name = nullptr;
        const char* version = nullptr;
        int32_t type = ANEURALNETWORKS_DEVICE_UNKNOWN;
        int64_t feature_level = 0;

        status = get_device(index, &device);
        if (status == ANEURALNETWORKS_NO_ERROR) status = get_name(device, &name);
        if (status == ANEURALNETWORKS_NO_ERROR) status = get_type(device, &type);
        if (status == ANEURALNETWORKS_NO_ERROR) status = get_version(device, &version);
        if (status == ANEURALNETWORKS_NO_ERROR) {
            status = get_feature_level(device, &feature_level);
        }
        if (status != ANEURALNETWORKS_NO_ERROR) {
            dlclose(library);
            throw_runtime_error(env, nnapi_error("NNAPI device query", status, index));
            return nullptr;
        }

        const std::string fields[] = {
                std::to_string(index),
                name == nullptr ? "" : name,
                std::to_string(type),
                version == nullptr ? "" : version,
                std::to_string(feature_level),
        };
        for (int field = 0; field < 5; ++field) {
            jstring value = env->NewStringUTF(fields[field].c_str());
            if (value == nullptr) {
                dlclose(library);
                return nullptr;
            }
            env->SetObjectArrayElement(
                    values, static_cast<jsize>(index * 5 + field), value);
            env->DeleteLocalRef(value);
            if (env->ExceptionCheck()) {
                dlclose(library);
                return nullptr;
            }
        }
    }

    dlclose(library);
    return values;
}
