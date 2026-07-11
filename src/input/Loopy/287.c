// Source: data/benchmarks/code2inv/5.c

void loopy_287(int size, int y, int z)
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