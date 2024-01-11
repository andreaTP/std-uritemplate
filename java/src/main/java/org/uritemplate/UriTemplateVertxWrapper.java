package org.uritemplate;

import io.vertx.uritemplate.Variables;

import java.util.List;
import java.util.Map;

public class UriTemplateVertxWrapper implements UriTemplate {
    private String template = null;
    private Variables substs = null;

    public void prepare(String template, Map<String, Object> substitutions) {
        this.template = template;
        Variables vars = Variables.variables();
        for (var e: substitutions.entrySet()) {
            if (e.getKey().equals("geocode")) {
                vars.set(e.getKey(), (List<String>)e.getValue());
            } else {
                vars.set(e.getKey(), (String)e.getValue());
            }
        }
        substs = vars;
    }
    @Override
    public String benchmark() {
        return io.vertx.uritemplate.UriTemplate.of(template).expandToString(substs);
    }
}
