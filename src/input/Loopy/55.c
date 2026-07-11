// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loop-lit/ddlm2013_true-unreach-call.c
extern int unknown_int(void);

void loopy_55(unsigned int i, int flag) {
    unsigned int j, a, b;
    
    a = 0;
    b = 0;
    j = 1;
    if (flag) {
        i = 0;
    } else {
        i = 1;
    }

    while (unknown_int()) {
        a++;
        b += (j - i);
        i += 2;
        if (i%2 == 0) {
            j += 2;
        } else {
            j++;
        }
    }
    if (flag) {
        {;
//@ assert(a == b);
}

    }
    return;
}