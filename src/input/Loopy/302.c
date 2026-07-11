// Source: data/benchmarks/code2inv/65.c

void loopy_302(int y) {
    int x = 1;
    

    while (x <= 100) {
        y = 100 - x;
        x = x +1;
    }

    {;
//@ assert(y >= 0);
}

}