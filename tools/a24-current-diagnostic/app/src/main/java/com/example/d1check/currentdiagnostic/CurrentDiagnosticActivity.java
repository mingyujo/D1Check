package com.example.d1check.currentdiagnostic;

import android.app.Activity;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Debug;
import android.os.PowerManager;
import android.os.SystemClock;
import android.opengl.*;
import android.util.Base64;
import android.widget.TextView;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

/** Separate synthetic excitation diagnostic. No model, scheduling policy, or J calibration. */
public class CurrentDiagnosticActivity extends Activity {
    private final Object logLock = new Object();
    private final AtomicReference<String> failure = new AtomicReference<>();
    private final ScheduledExecutorService sampler = Executors.newSingleThreadScheduledExecutor();
    private ScheduledFuture<?> sampling;
    private FileOutputStream stream;
    private File output;
    private JSONObject config;
    private String sid;
    private long sequence, started, wallStop;
    private volatile String phase = "SETUP";
    private volatile long currentPeriod = 900;
    private volatile double sink;
    private EGLDisplay display;
    private EGLContext context;
    private EGLSurface surface;
    private int program;

    private long now() { return SystemClock.elapsedRealtimeNanos(); }
    private static JSONObject object(Object... pairs) throws JSONException {
        JSONObject x = new JSONObject();
        for (int i=0;i<pairs.length;i+=2) x.put((String)pairs[i], pairs[i+1] == null ? JSONObject.NULL : pairs[i+1]);
        return x;
    }
    private void event(String kind, JSONObject x) throws Exception {
        synchronized (logLock) {
            x.put("kind",kind);x.put("mono_ns",now());x.put("sequence",sequence++);x.put("session_id",sid);x.put("phase",phase);
            stream.write((x+"\n").getBytes(StandardCharsets.UTF_8));stream.flush();
        }
    }
    private void write(String name, JSONObject x) throws Exception {
        File part = new File(output,name+".part"), target = new File(output,name);
        if (target.exists() || !part.createNewFile()) throw new IOException("write-once artifact exists");
        try (FileOutputStream f = new FileOutputStream(part)) { f.write((x+"\n").getBytes(StandardCharsets.UTF_8));f.flush();f.getFD().sync(); }
        if (!part.renameTo(target)) throw new IOException("atomic rename failed");
    }
    private static String sha(File f) throws Exception {
        MessageDigest m=MessageDigest.getInstance("SHA-256");byte[] b=new byte[1024*1024];
        try(InputStream s=new FileInputStream(f)){int n;while((n=s.read(b))>0)m.update(b,0,n);}
        StringBuilder out=new StringBuilder();for(byte v:m.digest())out.append(String.format("%02x",v&255));return out.toString();
    }
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        setContentView(new TextView(this) {{ setText("A24 전류 반응 진단 · 별도 합성 부하\n정책 성능·절대 에너지 검증 아님"); }});
        if(saved!=null || !getIntent().getBooleanExtra("execute_authorized",false)){finish();return;}
        getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        new Thread(()->runDiagnostic(),"diagnostic-control-and-load").start();
    }
    private void healthy() {
        if(failure.get()!=null)throw new IllegalStateException(failure.get());
        if(System.currentTimeMillis()>=wallStop || now()-started>900_000_000_000L)throw new IllegalStateException("bounded diagnostic deadline");
    }
    private void sample() {
        try {
            healthy();
            BatteryManager b=getSystemService(BatteryManager.class);
            long s=now(),cpuStart=Debug.threadCpuTimeNanos();
            long cs=now();int current=b.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW);long ce=now();
            long as=now();int average=b.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_AVERAGE);long ae=now();
            Intent battery=registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
            PowerManager pm=getSystemService(PowerManager.class);
            int plugged=battery==null?-1:battery.getIntExtra(BatteryManager.EXTRA_PLUGGED,-1);
            int level=battery==null?-1:battery.getIntExtra(BatteryManager.EXTRA_LEVEL,-1);
            int scale=battery==null?-1:battery.getIntExtra(BatteryManager.EXTRA_SCALE,-1);
            int temp=battery==null?-1:battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,-1);
            int thermal=Build.VERSION.SDK_INT>=29?pm.getCurrentThermalStatus():-1;
            long e=now(),cpuEnd=Debug.threadCpuTimeNanos();
            event("sensor_sample",object("read_start_ns",s,"read_end_ns",e,"current_read_start_ns",cs,"current_read_end_ns",ce,
                "average_read_start_ns",as,"average_read_end_ns",ae,"current_raw",current==Integer.MIN_VALUE?null:current,
                "average_current_raw",average==Integer.MIN_VALUE?null:average,"current_unit","API_uA_DEVICE_UNVERIFIED",
                "sensor_acquisition_ns",null,"voltage_raw_mV",battery==null?null:battery.getIntExtra(BatteryManager.EXTRA_VOLTAGE,-1),
                "battery_level",level,"battery_scale",scale,"plugged",plugged,"battery_temperature_deci_c",temp,
                "thermal_status",thermal,"interactive",pm.isInteractive(),"requested_period_ms",currentPeriod,"sampler_thread_cpu_ns",cpuEnd-cpuStart));
            if(plugged!=0 || scale<=0 || level*100L<10L*scale || temp<0 || temp>350 || !pm.isInteractive() || thermal>=3)
                failure.compareAndSet(null,"battery/screen/thermal safety");
        } catch(Throwable e) { failure.compareAndSet(null,"sampler: "+e); }
    }
    private void sampling(long period) throws Exception {
        if(sampling!=null){sampling.cancel(false);sampler.submit(()->{}).get(5,TimeUnit.SECONDS);}
        currentPeriod=period;
        event("sample_period_change",object("period_ms",period));
        sampling=sampler.scheduleAtFixedRate(this::sample,0,period,TimeUnit.MILLISECONDS);
    }
    private void idle(double seconds) throws Exception {
        long until=now()+(long)(seconds*1e9);
        while(now()<until){healthy();Thread.sleep(Math.max(1,Math.min(50,(until-now())/1_000_000L)));}
    }
    private int shader(int type,String text){
        int s=GLES30.glCreateShader(type);GLES30.glShaderSource(s,text);GLES30.glCompileShader(s);int[] ok={0};GLES30.glGetShaderiv(s,GLES30.GL_COMPILE_STATUS,ok,0);
        if(ok[0]==0)throw new IllegalStateException("shader: "+GLES30.glGetShaderInfoLog(s));return s;
    }
    private void prepareGpu() throws Exception {
        display=EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);int[] v=new int[2];
        if(!EGL14.eglInitialize(display,v,0,v,1))throw new IllegalStateException("EGL initialize");
        int[] attrs={EGL14.EGL_RENDERABLE_TYPE,0x40,EGL14.EGL_SURFACE_TYPE,EGL14.EGL_PBUFFER_BIT,EGL14.EGL_RED_SIZE,8,EGL14.EGL_GREEN_SIZE,8,EGL14.EGL_BLUE_SIZE,8,EGL14.EGL_NONE};
        EGLConfig[] configs=new EGLConfig[1];int[] count={0};
        if(!EGL14.eglChooseConfig(display,attrs,0,configs,0,1,count,0)||count[0]!=1)throw new IllegalStateException("ES3 pbuffer unavailable");
        context=EGL14.eglCreateContext(display,configs[0],EGL14.EGL_NO_CONTEXT,new int[]{EGL14.EGL_CONTEXT_CLIENT_VERSION,3,EGL14.EGL_NONE},0);
        surface=EGL14.eglCreatePbufferSurface(display,configs[0],new int[]{EGL14.EGL_WIDTH,256,EGL14.EGL_HEIGHT,256,EGL14.EGL_NONE},0);
        if(!EGL14.eglMakeCurrent(display,surface,surface,context))throw new IllegalStateException("EGL makeCurrent");
        int vertex=shader(GLES30.GL_VERTEX_SHADER,"#version 300 es\nvoid main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);gl_Position=vec4(p*2.0-1.0,0,1);}");
        int fragment=shader(GLES30.GL_FRAGMENT_SHADER,"#version 300 es\nprecision highp float;uniform float tick;out vec4 outColor;void main(){vec2 x=gl_FragCoord.xy/257.0+tick;for(int i=0;i<128;i++){x=sin(x.yx*1.17+vec2(0.13,0.27));}outColor=vec4(x*0.5+0.5,0.5,1.0);}");
        program=GLES30.glCreateProgram();GLES30.glAttachShader(program,vertex);GLES30.glAttachShader(program,fragment);GLES30.glLinkProgram(program);int[] ok={0};GLES30.glGetProgramiv(program,GLES30.GL_LINK_STATUS,ok,0);
        if(ok[0]==0)throw new IllegalStateException("GPU link: "+GLES30.glGetProgramInfoLog(program));
        GLES30.glDeleteShader(vertex);GLES30.glDeleteShader(fragment);GLES30.glUseProgram(program);GLES30.glViewport(0,0,256,256);
        event("gpu_ready",object("renderer",GLES30.glGetString(GLES30.GL_RENDERER),"version",GLES30.glGetString(GLES30.GL_VERSION),"synthetic_load",true));
    }
    private void load(String resource,double seconds) throws Exception {
        healthy();long begin=now(),until=begin+(long)(seconds*1e9),iterations=0;
        event("load_start",object("resource",resource,"execution_boundary_ns",begin,"hardware_power_onset_known",false));
        double value=0.1234567;
        while(now()<until){
            healthy();long bs=now();
            if(resource.equals("CPU")){
                for(int k=0;k<20000;k++) value=Math.sin(value+0.00123)*Math.cos(value+0.9123)+0.41;
                sink=value;
            } else {
                GLES30.glUniform1f(GLES30.glGetUniformLocation(program,"tick"),(float)((iterations%97)/97.0));
                GLES30.glDrawArrays(GLES30.GL_TRIANGLES,0,3);GLES30.glFinish();
                int error=GLES30.glGetError();if(error!=GLES30.GL_NO_ERROR)throw new IllegalStateException("GPU error "+error);
            }
            long be=now();
            if(iterations%20==0)event("load_batch",object("resource",resource,"batch_start_ns",bs,"batch_end_ns",be,"batch_index",iterations,"GPU_completion_boundary",resource.equals("GPU")?"glFinish_return":JSONObject.NULL));
            iterations++;
        }
        long end=now();event("load_end",object("resource",resource,"execution_boundary_ns",end,"actual_duration_ns",end-begin,"batches",iterations));
    }
    private void runDiagnostic() {
        String status="FAILED_PRESERVED",reason="setup incomplete";int pulses=0;
        try {
            sid=getIntent().getStringExtra("session_id");if(!UUID.fromString(sid).toString().equals(sid))throw new IllegalArgumentException("session UUID");
            byte[] bytes=Base64.decode(getIntent().getStringExtra("config_base64"),Base64.NO_WRAP);
            config=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
            if(!config.getString("schema").equals("a24-current-response-diagnostic-v1") || !config.getString("session_id").equals(sid) || !config.getString("fingerprint").equals(Build.FINGERPRINT))throw new IllegalArgumentException("diagnostic identity");
            if(!config.getString("apk_sha256").equals(sha(new File(getApplicationInfo().sourceDir))))throw new IllegalArgumentException("APK SHA");
            wallStop=config.getLong("hard_stop_wall_ms");started=now();healthy();
            output=new File(getFilesDir(),"diagnostics/"+sid);if(!output.mkdirs())throw new IOException("diagnostic already exists; no replay");
            stream=new FileOutputStream(new File(output,"events.jsonl"));write("config.json",config);
            write("identity.json",object("session_id",sid,"process_id",android.os.Process.myPid(),"apk_sha256",config.getString("apk_sha256"),"fingerprint",Build.FINGERPRINT,"physical_J_validated",false,"synthetic_CPU_GPU_not_inference",true));
            event("diagnostic_start",object("host_start_time_is_not_sensor_time",true));
            sampling(900);prepareGpu();phase="SETTLE";idle(config.getDouble("settle_seconds"));
            JSONArray controls=config.getJSONArray("idle_control_periods_ms");
            for(int i=0;i<controls.length();i++){phase="CONTROL_"+i;sampling(controls.getLong(i));event("phase_start",object("role","idle_sampling_control"));idle(config.getDouble("idle_control_seconds"));event("phase_end",object());}
            JSONArray schedule=config.getJSONArray("pulses");
            for(int i=0;i<schedule.length();i++){
                JSONObject p=schedule.getJSONObject(i);sampling(p.getLong("period_ms"));
                phase="PULSE_"+i+"_PRE";event("phase_start",object("pulse",i,"split",p.getString("split"),"resource",p.getString("resource")));idle(p.getDouble("pre_seconds"));
                phase="PULSE_"+i+"_ON";load(p.getString("resource"),p.getDouble("on_seconds"));
                phase="PULSE_"+i+"_POST";idle(p.getDouble("post_seconds"));event("phase_end",object("pulse",i));pulses++;
            }
            phase="TAIL";sampling(200);idle(config.getDouble("final_tail_seconds"));healthy();status="COMPLETE_DIAGNOSTIC";reason="registered schedule finished";
        } catch(Throwable e) { reason=e.toString();try{if(stream!=null)event("failure",object("reason",reason));}catch(Throwable ignored){} }
        finally {
            if(sampling!=null)sampling.cancel(false);sampler.shutdown();try{sampler.awaitTermination(10,TimeUnit.SECONDS);}catch(InterruptedException ignored){}
            try{
                if(display!=null){if(program!=0)GLES30.glDeleteProgram(program);EGL14.eglMakeCurrent(display,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_CONTEXT);if(surface!=null)EGL14.eglDestroySurface(display,surface);if(context!=null)EGL14.eglDestroyContext(display,context);EGL14.eglTerminate(display);}
                if(stream!=null){event("diagnostic_end",object("status",status,"reason",reason,"completed_pulses",pulses));stream.flush();stream.getFD().sync();stream.close();write("summary.json",object("status",status,"reason",reason,"completed_pulses",pulses,"elapsed_ns",now()-started,"physical_J_validated",false));write("journal_closed.json",object("status","SYNCED_AND_CLOSED","session_id",sid,"process_id",android.os.Process.myPid(),"events_sha256",sha(new File(output,"events.jsonl")),"sampler_terminated",sampler.isTerminated()));}
            }catch(Throwable e){android.util.Log.e("A24CurrentDiag","closure failed",e);}
            runOnUiThread(this::finish);
        }
    }
}
