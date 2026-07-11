// Source: data/benchmarks/code2inv/6.c

void loopy_298(int v1, int v2, int v3, int size, int y, int z)
{
    
    int x = 0;
    
    

    while(x < size) {
       x += 1;
       if( z <= y) {
          y = z;
       }
    }

    if(size > 0) {
       {;
//@ assert(z >= y);
}

    }
}